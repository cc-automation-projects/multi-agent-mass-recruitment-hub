terraform {
  required_providers {
    yandex = {
      source = "yandex-cloud/yandex"
      version = "~> 0.100"
    }
    helm = {
      source = "hashicorp/helm"
      version = "~> 2.12"
    }
  }
}

provider "yandex" {
  cloud_id  = var.cloud_id
  folder_id = var.folder_id
  zone      = var.zone
}

resource "yandex_kubernetes_cluster" "cluster" {
  name = "mass-recruit-hub-prod"
  network_id = yandex_vpc_network.main.id
  master {
    version = "1.29"
    regional {
      region = "ru-central1"
    }
  }
  service_account_id = yandex_iam_service_account.k8s.id
  node_service_account_id = yandex_iam_service_account.k8s.id
}

resource "yandex_kubernetes_node_group" "apps" {
  cluster_id = yandex_kubernetes_cluster.cluster.id
  name = "app-node-group"
  instance_template {
    platform_id = "standard-v3"
    resources {
      cores = 4
      memory = 8
    }
    boot_disk {
      size = 64
      type = "network-ssd"
    }
    labels = {
      node_group = "app"
    }
  }
  scale_policy {
    auto_scale {
      min = 3
      max = 10
      initial = 3
    }
  }
}

resource "yandex_mdb_postgresql_cluster" "pg" {
  name = "mass-recruit-hub-pg"
  environment = "PRODUCTION"
  network_id = yandex_vpc_network.main.id
  version = "16"
  resources {
    resource_preset_id = "s4-c2-m8"
    disk_size = 100
    disk_type_id = "network-ssd"
  }
  host {
    zone = "ru-central1-a"
    subnet_id = yandex_vpc_subnet.subnet_a.id
  }
  host {
    zone = "ru-central1-b"
    subnet_id = yandex_vpc_subnet.subnet_b.id
  }
  config {
    pooler {
      pooling_mode = "TRANSACTION"
    }
  }
}

resource "yandex_mdb_redis_cluster" "redis" {
  name = "mass-recruit-hub-redis"
  environment = "PRODUCTION"
  network_id = yandex_vpc_network.main.id
  version = "7.2"
  resources {
    resource_preset_id = "hm2-c2-m4"
    disk_size = 32
  }
  host {
    zone = "ru-central1-a"
    subnet_id = yandex_vpc_subnet.subnet_a.id
  }
  config {
    password = var.redis_password
  }
}

resource "yandex_storage_bucket" "audio" {
  bucket = "mass-recruit-hub-audio-prod"
  acl    = "private"
}

resource "yandex_vpc_network" "main" {
  name = "mass-recruit-hub-network"
}

resource "yandex_vpc_subnet" "subnet_a" {
  name           = "ru-central1-a"
  zone           = "ru-central1-a"
  network_id     = yandex_vpc_network.main.id
  v4_cidr_blocks = ["10.1.0.0/24"]
}

resource "yandex_vpc_subnet" "subnet_b" {
  name           = "ru-central1-b"
  zone           = "ru-central1-b"
  network_id     = yandex_vpc_network.main.id
  v4_cidr_blocks = ["10.2.0.0/24"]
}
