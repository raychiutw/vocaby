#!/usr/bin/env ruby

require "base64"
require "json"
require "net/http"
require "openssl"
require "optparse"
require "time"
require "uri"

module TestFlightStatus
  API_ORIGIN = "https://api.appstoreconnect.apple.com"
  READY_INTERNAL_STATES = %w[READY_FOR_BETA_TESTING IN_BETA_TESTING].freeze
  FAILED_PROCESSING_STATES = %w[FAILED INVALID].freeze
  FAILED_INTERNAL_STATES = %w[
    PROCESSING_EXCEPTION
    MISSING_EXPORT_COMPLIANCE
    EXPIRED
  ].freeze

  class APIError < StandardError
    attr_reader :status

    def initialize(status, message)
      @status = status
      super(message)
    end

    def retryable?
      status == 429 || status >= 500
    end
  end

  module_function

  def base64url(value)
    Base64.urlsafe_encode64(value).delete("=")
  end

  def jwt(private_key_pem:, key_id:, issuer_id:, now: Time.now)
    header = base64url(JSON.generate(alg: "ES256", kid: key_id, typ: "JWT"))
    payload = base64url(
      JSON.generate(
        iss: issuer_id,
        iat: now.to_i - 5,
        exp: now.to_i + 1_200,
        aud: "appstoreconnect-v1"
      )
    )
    signing_input = "#{header}.#{payload}"
    key = OpenSSL::PKey.read(private_key_pem)
    digest = OpenSSL::Digest::SHA256.digest(signing_input)
    sequence = OpenSSL::ASN1.decode(key.dsa_sign_asn1(digest))
    signature = sequence.value.map do |integer|
      integer.value.to_s(2).rjust(32, "\0")[-32, 32]
    end.join

    "#{signing_input}.#{base64url(signature)}"
  end

  def request(path, token)
    uri = URI("#{API_ORIGIN}#{path}")
    request = Net::HTTP::Get.new(uri)
    request["Authorization"] = "Bearer #{token}"
    request["Accept"] = "application/json"

    response = Net::HTTP.start(
      uri.host,
      uri.port,
      use_ssl: true,
      open_timeout: 15,
      read_timeout: 30
    ) { |http| http.request(request) }

    unless response.is_a?(Net::HTTPSuccess)
      detail = begin
        JSON.parse(response.body).fetch("errors", []).map do |error|
          error["detail"] || error["title"]
        end.compact.join("; ")
      rescue JSON::ParserError
        ""
      end
      detail = "App Store Connect API request failed" if detail.empty?
      raise APIError.new(response.code.to_i, "HTTP #{response.code}: #{detail}")
    end

    JSON.parse(response.body)
  end

  def path_with_query(path, parameters)
    "#{path}?#{URI.encode_www_form(parameters)}"
  end

  def app_id(bundle_id, token)
    response = request(
      path_with_query(
        "/v1/apps",
        "filter[bundleId]" => bundle_id,
        "fields[apps]" => "bundleId,name",
        "limit" => "1"
      ),
      token
    )
    app = response.fetch("data").first
    raise "No App Store Connect app found for #{bundle_id}" unless app

    app.fetch("id")
  end

  def build(app_id:, public_version:, build_number:, token:)
    response = request(
      path_with_query(
        "/v1/builds",
        "filter[app]" => app_id,
        "filter[version]" => build_number,
        "filter[preReleaseVersion.version]" => public_version,
        "fields[builds]" => "version,uploadedDate,processingState,expired,usesNonExemptEncryption,buildBetaDetail",
        "sort" => "-uploadedDate",
        "limit" => "1"
      ),
      token
    )
    response.fetch("data").first
  end

  def beta_detail(build_id, token)
    response = request(
      path_with_query(
        "/v1/builds/#{build_id}/buildBetaDetail",
        "fields[buildBetaDetails]" => "internalBuildState,externalBuildState,autoNotifyEnabled"
      ),
      token
    )
    response.fetch("data").fetch("attributes")
  end

  def log(message)
    puts "[#{Time.now.utc.iso8601}] #{message}"
    $stdout.flush
  end

  def wait(bundle_id:, public_version:, build_number:, private_key_pem:, key_id:, issuer_id:, timeout:, interval:)
    deadline = Process.clock_gettime(Process::CLOCK_MONOTONIC) + timeout
    resolved_app_id = nil

    loop do
      begin
        token = jwt(
          private_key_pem: private_key_pem,
          key_id: key_id,
          issuer_id: issuer_id
        )
        resolved_app_id ||= app_id(bundle_id, token)
        current_build = build(
          app_id: resolved_app_id,
          public_version: public_version,
          build_number: build_number,
          token: token
        )

        if current_build.nil?
          log("TestFlight #{public_version} (#{build_number}) is not visible yet")
        else
          attributes = current_build.fetch("attributes")
          processing_state = attributes.fetch("processingState")
          log("TestFlight #{public_version} (#{build_number}) processingState=#{processing_state}")

          if FAILED_PROCESSING_STATES.include?(processing_state)
            raise "TestFlight processing failed with #{processing_state}"
          end

          if processing_state == "VALID"
            begin
              detail = beta_detail(current_build.fetch("id"), token)
              internal_state = detail.fetch("internalBuildState")
              external_state = detail["externalBuildState"]
              log("internalBuildState=#{internal_state} externalBuildState=#{external_state}")

              if READY_INTERNAL_STATES.include?(internal_state)
                log("TestFlight #{public_version} (#{build_number}) is ready for internal testing")
                return
              end

              if FAILED_INTERNAL_STATES.include?(internal_state)
                raise "TestFlight is not available: internalBuildState=#{internal_state}"
              end
            rescue APIError => error
              raise unless error.status == 404

              log("TestFlight beta details are not visible yet")
            end
          end
        end
      rescue APIError => error
        raise unless error.retryable?

        log("Retryable App Store Connect response: #{error.message}")
      end

      remaining = deadline - Process.clock_gettime(Process::CLOCK_MONOTONIC)
      raise "Timed out waiting for TestFlight processing" if remaining <= 0

      sleep [interval, remaining].min
    end
  end
end

if $PROGRAM_NAME == __FILE__
  options = {
    bundle_id: "com.raychiutw.Vocaby",
    timeout: 1_800,
    interval: 30
  }

  OptionParser.new do |parser|
    parser.banner = "Usage: wait_for_testflight.rb --version VERSION --build-number BUILD"
    parser.on("--bundle-id BUNDLE_ID") { |value| options[:bundle_id] = value }
    parser.on("--version VERSION") { |value| options[:public_version] = value }
    parser.on("--build-number BUILD") { |value| options[:build_number] = value }
    parser.on("--timeout SECONDS", Integer) { |value| options[:timeout] = value }
    parser.on("--interval SECONDS", Integer) { |value| options[:interval] = value }
  end.parse!

  required = {
    "--version" => options[:public_version],
    "--build-number" => options[:build_number],
    "ASC_KEY_PATH" => ENV["ASC_KEY_PATH"],
    "ASC_KEY_ID" => ENV["ASC_KEY_ID"],
    "ASC_ISSUER_ID" => ENV["ASC_ISSUER_ID"]
  }
  missing = required.select { |_name, value| value.nil? || value.empty? }.keys
  abort "Missing #{missing.join(', ')}" unless missing.empty?

  begin
    TestFlightStatus.wait(
      bundle_id: options.fetch(:bundle_id),
      public_version: options.fetch(:public_version),
      build_number: options.fetch(:build_number),
      private_key_pem: File.read(ENV.fetch("ASC_KEY_PATH")),
      key_id: ENV.fetch("ASC_KEY_ID"),
      issuer_id: ENV.fetch("ASC_ISSUER_ID"),
      timeout: options.fetch(:timeout),
      interval: options.fetch(:interval)
    )
  rescue StandardError => error
    warn error.message
    exit 1
  end
end
