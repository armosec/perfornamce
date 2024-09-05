#
# VPC Resources
#  * VPC
#  * Subnets
#  * Internet Gateway
#  * Route Table
#

resource "aws_vpc" "cluster_vpc" {
  cidr_block = "10.0.0.0/16"

  tags = {
    Name                                          = local.vpc_name
    "kubernetes.io/cluster/${local.cluster_name}" = "shared"
    Owner                                         = local.owner
  }
}

resource "aws_subnet" "subnet" {
  count = var.subnet_count

  availability_zone       = data.aws_availability_zones.available.names[count.index]
  cidr_block              = "10.0.${count.index * 8}.0/21"
  map_public_ip_on_launch = true
  vpc_id                  = aws_vpc.cluster_vpc.id

  tags = {
    Name                                          = "${local.owner}-subnet"
    "kubernetes.io/cluster/${local.cluster_name}" = "shared"
    Owner                                         = local.owner
  }
}

resource "aws_internet_gateway" "internet_gateway" {
  vpc_id = aws_vpc.cluster_vpc.id

  tags = {
    Name  = "${local.owner}-ig"
    Owner = local.owner
  }
}

resource "aws_route_table" "route_table" {
  vpc_id = aws_vpc.cluster_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.internet_gateway.id
  }
}

resource "aws_route_table_association" "route_table_association" {
  count = 2

  subnet_id      = aws_subnet.subnet[count.index].id
  route_table_id = aws_route_table.route_table.id
}