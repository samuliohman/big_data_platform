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
    ports    = ["7000", "7002", "9042", "22"]  #  port 22 for SSH
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

  metadata_startup_script = <<-EOF
#!/bin/bash

# Update the system
sudo apt-get update -y
sudo apt-get upgrade -y

# Install OpenJDK as a prerequisite
sudo apt-get install openjdk-11-jdk -y

# Create the keyrings directory if it doesn't exist
sudo mkdir -p /etc/apt/keyrings

# Download the Apache Cassandra GPG key and store it securely
curl -o /etc/apt/keyrings/apache-cassandra.asc https://downloads.apache.org/cassandra/KEYS

# Add the Cassandra repository for the 4.1 series
echo "deb [signed-by=/etc/apt/keyrings/apache-cassandra.asc] https://debian.cassandra.apache.org 41x main" | sudo tee /etc/apt/sources.list.d/cassandra.sources.list

# Update the package list
sudo apt-get update

# Install Cassandra
sudo apt-get install cassandra -y

# Stop Cassandra until custom cassadra.yaml is in place
sudo systemctl enable cassandra
sudo systemctl stop cassandra
sudo chown -R cassandra:cassandra /var/lib/cassandra
sudo chown cassandra:cassandra /etc/cassandra/cassandra.yaml
EOF
}

resource "google_compute_instance" "eu_west_node" {
  name         = "eu-west-node"
  machine_type = "e2-standard-2"
  zone         = "europe-west1-b"  # updated zone for Europe West

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
    }
  }

  network_interface {
    network    = google_compute_network.cassandra-network.name
    access_config {}
  }

  metadata_startup_script = <<-EOF
#!/bin/bash

# Update the system
sudo apt-get update -y
sudo apt-get upgrade -y

# Install OpenJDK as a prerequisite
sudo apt-get install openjdk-11-jdk -y

# Create the keyrings directory if it doesn't exist
sudo mkdir -p /etc/apt/keyrings

# Download the Apache Cassandra GPG key and store it securely
curl -o /etc/apt/keyrings/apache-cassandra.asc https://downloads.apache.org/cassandra/KEYS

# Add the Cassandra repository for the 4.1 series
echo "deb [signed-by=/etc/apt/keyrings/apache-cassandra.asc] https://debian.cassandra.apache.org 41x main" | sudo tee /etc/apt/sources.list.d/cassandra.sources.list

# Update the package list
sudo apt-get update

# Install Cassandra
sudo apt-get install cassandra -y

# Stop Cassandra until custom cassadra.yaml is in place
sudo systemctl enable cassandra
sudo systemctl stop cassandra
sudo chown -R cassandra:cassandra /var/lib/cassandra
sudo chown cassandra:cassandra /etc/cassandra/cassandra.yaml
EOF
}

data "google_compute_instance" "nordics_node_ip" {
  name = google_compute_instance.nordics_node.name
  zone = google_compute_instance.nordics_node.zone
}

data "google_compute_instance" "eu_west_node_ip" {
  name = google_compute_instance.eu_west_node.name
  zone = google_compute_instance.eu_west_node.zone
}
