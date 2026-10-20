# The "Thing" - AWS's representation of your physical smart plug
resource "aws_iot_thing" "smart_plug" {
  name = "orange-pi-smart-plug"
}

# X.509 certificate - the credential the device uses to connect
resource "aws_iot_certificate" "smart_plug" {
  active = true
}

# Attach the certificate to the Thing
resource "aws_iot_thing_principal_attachment" "smart_plug" {
  principal = aws_iot_certificate.smart_plug.arn
  thing     = aws_iot_thing.smart_plug.name
}

# Policy - scoped narrowly: this cert can ONLY publish to one specific topic
data "aws_iam_policy_document" "iot_publish_policy" {
  statement {
    effect    = "Allow"
    actions   = ["iot:Connect"]
    resources = ["arn:aws:iot:ap-southeast-1:*:client/orange-pi-smart-plug"]
  }

  statement {
    effect    = "Allow"
    actions   = ["iot:Publish"]
    resources = ["arn:aws:iot:ap-southeast-1:*:topic/plug/readings"]
  }
}

resource "aws_iot_policy" "smart_plug" {
  name   = "smart-plug-publish-only"
  policy = data.aws_iam_policy_document.iot_publish_policy.json
}

# Attach the policy to the certificate
resource "aws_iot_policy_attachment" "smart_plug" {
  policy = aws_iot_policy.smart_plug.name
  target = aws_iot_certificate.smart_plug.arn
}

# Output the certificate PEM and private key so we can save them to the device
# Note: these are sensitive and only available immediately after creation
output "certificate_pem" {
  value     = aws_iot_certificate.smart_plug.certificate_pem
  sensitive = true
}

output "private_key" {
  value     = aws_iot_certificate.smart_plug.private_key
  sensitive = true
}

# IoT Core's regional endpoint - the address your device connects to
data "aws_iot_endpoint" "current" {
  endpoint_type = "iot:Data-ATS"
}

output "iot_endpoint" {
  value = data.aws_iot_endpoint.current.endpoint_address
}
