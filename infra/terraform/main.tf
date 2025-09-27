#################################
# Terraform / Provider
#################################
terraform {
  required_providers {
    yandex = {
      source = "yandex-cloud/yandex"
    }
  }
  required_version = ">= 0.13"
}

provider "yandex" {
  token     = var.yc_token
  cloud_id  = var.cloud_id
  folder_id = var.folder_id
  zone      = var.default_zone
}

#################################
# Base image
#################################

data "yandex_compute_image" "ubuntu" {
  family = "ubuntu-2404-lts-oslogin"
}

#################################
# Network
#################################

resource "yandex_vpc_network" "default" {
  name = "default-net"
}

resource "yandex_vpc_subnet" "default" {
  name           = "default-subnet"
  zone           = var.default_zone
  network_id     = yandex_vpc_network.default.id
  v4_cidr_blocks = ["10.0.0.0/24"]
}

#################################
# Compute instances
#################################

resource "yandex_compute_instance" "vm_portal" {
  name        = "vm_portal"
  platform_id = "standard-v2"
  zone        = var.default_zone

  resources {
    cores  = 2
    memory = 2
  }

  boot_disk {
    initialize_params {
      image_id = data.yandex_compute_image.ubuntu.id
      size     = 10
    }
  }

  network_interface {
    subnet_id = yandex_vpc_subnet.default.id
    nat       = true
  }

  scheduling_policy {
    preemptible = true
  }

  metadata = {
    enable-oslogin = true
  }
}

resource "yandex_compute_instance" "vm_gitlab" {
  name        = "vm_gitlab"
  allow_stopping_for_update = true
  platform_id = "standard-v2"
  zone        = var.default_zone

  resources {
    cores  = 2
    memory = 6
  }

  boot_disk {
    initialize_params {
      image_id = data.yandex_compute_image.ubuntu.id
      size     = 20
    }
  }

  network_interface {
    subnet_id = yandex_vpc_subnet.default.id
    nat       = true
  }

  scheduling_policy {
    preemptible = true
  }

  metadata = {
    enable-oslogin = true
  }
}

resource "yandex_compute_instance" "vm_jira" {
  name        = "vm_jira"
  platform_id = "standard-v2"
  zone        = var.default_zone

  resources {
    cores  = 2
    memory = 4
  }

  boot_disk {
    initialize_params {
      image_id = data.yandex_compute_image.ubuntu.id
      size     = 20
    }
  }

  network_interface {
    subnet_id = yandex_vpc_subnet.default.id
    nat       = true
  }

  scheduling_policy {
    preemptible = true
  }

  metadata = {
    enable-oslogin = true
  }
}

resource "yandex_compute_instance" "vm_grafana" {
  name        = "vm_grafana"
  platform_id = "standard-v2"
  zone        = var.default_zone

  resources {
    cores  = 2
    memory = 4
  }

  boot_disk {
    initialize_params {
      image_id = data.yandex_compute_image.ubuntu.id
      size     = 20
    }
  }

  network_interface {
    subnet_id = yandex_vpc_subnet.default.id
    nat       = true
  }

  scheduling_policy {
    preemptible = true
  }

  metadata = {
    enable-oslogin = true
  }
}

#################################
# DNS: Public zone + A records
#################################

resource "yandex_dns_zone" "public" {
  name   = "feebee-public-zone"
  zone   = var.public_zone   # "feebee.ru."
  public = true
}

resource "yandex_dns_recordset" "pub_portal" {
  zone_id = yandex_dns_zone.public.id
  name    = "${var.name_portal}.${yandex_dns_zone.public.zone}"   # portal.feebee.ru.
  type    = "A"
  ttl     = 120
  data    = [yandex_compute_instance.vm_portal.network_interface[0].nat_ip_address]
}

resource "yandex_dns_recordset" "pub_grafana" {
  zone_id = yandex_dns_zone.public.id
  name    = "${var.name_grafana}.${yandex_dns_zone.public.zone}"  # grafana.feebee.ru.
  type    = "A"
  ttl     = 120
  data    = [yandex_compute_instance.vm_grafana.network_interface[0].nat_ip_address]
}

resource "yandex_dns_recordset" "pub_jira" {
  zone_id = yandex_dns_zone.public.id
  name    = "${var.name_jira}.${yandex_dns_zone.public.zone}"     # jira.feebee.ru.
  type    = "A"
  ttl     = 120
  data    = [yandex_compute_instance.vm_jira.network_interface[0].nat_ip_address]
}

resource "yandex_dns_recordset" "pub_gitlab" {
  zone_id = yandex_dns_zone.public.id
  name    = "${var.name_gitlab}.${yandex_dns_zone.public.zone}"   # gitlab.feebee.ru.
  type    = "A"
  ttl     = 120
  data    = [yandex_compute_instance.vm_gitlab.network_interface[0].nat_ip_address]
}