provider "google" {
  project = "<your-gcp-project-id>"  # Replace with your GCP project ID
  region  = "europe-north1"
}

resource "google_compute_network" "cassandra-network" {
  name = "cassandra-network"
}

resource "google_compute_firewall" "cassandra-firewall" {
  name    = "cassandra-allow"
  network = google_compute_network.cassandra-network.name

  allow {
    protocol = "tcp"
    ports    = ["9042"]
  }

  source_ranges = ["0.0.0.0/0"]
}

resource "google_compute_instance" "nordics_node" {
  name         = "nordics-node"
  machine_type = "e2-standard-2"
  zone         = "europe-north1-a"

  boot_disk {
    initialize_params {
      image = "ubuntu-2204-jammy-v20230126"
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

resource "google_compute_instance" "asia_node" {
  name         = "asia-node"
  machine_type = "e2-standard-2"
  zone         = "asia-southeast1-a"

  boot_disk {
    initialize_params {
      image = "ubuntu-2204-jammy-v20230126"
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
    echo "Cassandra installed on asia node"
  EOT
}
