provider "google" {
  project = "bigdataplatform-449310"  # Replace with your GCP project ID
  region  = "europe-north1"
}

resource "google_compute_network" "cassandra-network" {
  name = "cassandra-network"
  auto_create_subnetworks = true  # Enable auto-creation of subnets
}

resource "google_compute_firewall" "cassandra-firewall" {
  name    = "cassandra-allow"
  network = google_compute_network.cassandra-network.name

  allow {
    protocol = "tcp"
    ports    = ["9042", "22"]  #  port 22 for SSH
  }

  source_ranges = ["0.0.0.0/0"]
}

resource "google_compute_instance" "nordics_node" {
  name         = "nordics-node"
  machine_type = "e2-standard-2"
  zone         = "europe-north1-a"

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
    }
  }

  network_interface {
    network = google_compute_network.cassandra-network.name
    access_config {}
  }

  metadata_startup_script = <<-EOT
    #!/bin/bash
    sudo apt update
    sudo apt install -y cassandra
    echo "Cassandra installed on nordics node"
  EOT
}

resource "google_compute_instance" "west_node" {
  name         = "west-node"
  machine_type = "e2-standard-2"
  zone         = "europe-west1-b"

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
    }
  }

  network_interface {
    network    = google_compute_network.cassandra-network.name
    subnetwork = google_compute_subnetwork.west_subnet.self_link
    access_config {}
  }

  provisioner "file" {
    source      = "cassandra.yaml"  # Path to your local cassandra.yaml file
    destination = "/etc/cassandra/cassandra.yaml"  # Destination on the VM
    
    connection {
      type        = "ssh"
      user        = "your-ssh-user"
      private_key = file("~/.ssh/google_compute_engine")
      host        = self.network_interface[0].access_config[0].nat_ip
    }
  }

  metadata_startup_script = <<-EOT
    #!/bin/bash
    sudo apt update
    sudo apt install -y cassandra
    echo "Cassandra installed on west node"
  EOT
}

resource "google_compute_subnetwork" "west_subnet" {
  name          = "west-subnet"
  ip_cidr_range = "10.0.0.0/20"
  region        = "europe-west1"
  network       = google_compute_network.cassandra-network.self_link
}
