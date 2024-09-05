terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "3.4.3"
    }
  }
  # backend "s3" {
  #   bucket = "ca-eks-test-clusters"
  #   key    = "${local.random}/"
  #   region = "eu-west-2"
  # }
}

provider "aws" {
  region = var.region
}


data "aws_availability_zones" "available" {}

resource "random_string" "suffix" {
  length  = 5
  upper   = false
  special = false
  # override_special = "/@£$"
}