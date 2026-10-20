data "aws_caller_identity" "current" {}

# ── S3 bucket (private) ────────────────────────────────────────────────────────
resource "aws_s3_bucket" "dashboard" {
  bucket = "plug-dashboard-${data.aws_caller_identity.current.account_id}"
  tags   = { Project = "homelab-iot" }
}

resource "aws_s3_bucket_public_access_block" "dashboard" {
  bucket                  = aws_s3_bucket.dashboard.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ── CloudFront OAC ─────────────────────────────────────────────────────────────
resource "aws_cloudfront_origin_access_control" "dashboard" {
  name                              = "plug-dashboard-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# ── CloudFront distribution ────────────────────────────────────────────────────
resource "aws_cloudfront_distribution" "dashboard" {
  origin {
    domain_name              = aws_s3_bucket.dashboard.bucket_regional_domain_name
    origin_id                = "S3-plug-dashboard"
    origin_access_control_id = aws_cloudfront_origin_access_control.dashboard.id
  }

  enabled             = true
  default_root_object = "index.html"
  price_class         = "PriceClass_100"

  # Redirect 404/403 errors to index.html for Single Page Application (SPA) routing (React/Vue)
  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 10
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 10
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-plug-dashboard"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }

    min_ttl     = 0
    default_ttl = 60
    max_ttl     = 300
  }

  restrictions {
    geo_restriction { restriction_type = "none" }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = { Project = "homelab-iot" }
}

# ── Bucket policy — allow CloudFront OAC only ─────────────────────────────────
resource "aws_s3_bucket_policy" "dashboard" {
  bucket = aws_s3_bucket.dashboard.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.dashboard.arn}/*"
      Condition = {
        StringEquals = {
          "AWS:SourceArn" = aws_cloudfront_distribution.dashboard.arn
        }
      }
    }]
  })
}

# ── Upload index.html ──────────────────────────────────────────────────────────
resource "aws_s3_object" "index_html" {
  bucket       = aws_s3_bucket.dashboard.id
  key          = "index.html"
  source       = "${path.module}/static/index.html"
  content_type = "text/html"
  etag         = filemd5("${path.module}/static/index.html")
}

output "cloudfront_url" {
  value       = "https://${aws_cloudfront_distribution.dashboard.domain_name}"
  description = "Public URL of the static SmartPlug dashboard"
}
