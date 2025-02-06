## Detailed project documentation is found in the file Project_document.pdf

### Here are instructions on how to replicate the big data platform creation
Notice the dataset (*.las files) have to be manually downloaded from https://archive.nyu.edu/handle/2451/38660 as they do not fit in the .zip

Initialize and Authenticate with Google Cloud SDK
Run these commands to set up and authenticate your Google Cloud environment:
```
gcloud init
gcloud auth login
gcloud auth application-default login
gcloud services enable compute.googleapis.com
```


Deploy Infrastructure Using Terraform
Use Terraform to initialize, apply, and configure the Cassandra cluster. Wait a few minutes for the nodes to be running before running the configuration script:
```
terraform init
terraform apply

# Configure cassandra using powershell script. Nodes need to be running before the script so wait a few minutes.
.\configure_cassandra.ps1

terraform destroy
```


Ingest Data into Cassandra
Once the Cassandra VMs are running, use these commands to ingest data:
```
cd data_ingestion
py -m pip install -r requirements.txt

# Get and use nodes' external IPs
$NORDICS_EXT_IP = gcloud compute instances describe nordics-node --zone=europe-north1-a --format="get(networkInterfaces[0].accessConfigs[0].natIP)"
$WEST_EXT_IP = gcloud compute instances describe eu-west-node --zone=europe-west1-b --format="get(networkInterfaces[0].accessConfigs[0].natIP)"

py data_ingestion.py --nodes "$NORDICS_EXT_IP" "$WEST_EXT_IP"
```


Debugging Commands
Use these commands to debug and monitor the status of your Cassandra nodes:
```
gcloud compute instances list

# Connect using SSH
gcloud compute ssh nordics-node --zone=europe-north1-a
gcloud compute ssh eu-west-node --zone=europe-west1-b
gcloud compute ssh nordics-node --zone=europe-north1-a --command="sudo journalctl -u google-startup-scripts"
gcloud compute ssh nordics-node --zone=europe-north1-a --command="sudo journalctl -l | grep cassandra"

# Check if Cassandra installed correctly
gcloud compute ssh nordics-node --zone=europe-north1-a --command="dpkg -l | grep cassandra"

# Check cassandra status
gcloud compute ssh nordics-node --zone=europe-north1-a --command="sudo systemctl status cassandra"
gcloud compute ssh nordics-node --zone=europe-north1-a --command="nodetool status"
gcloud compute ssh nordics-node --zone=europe-north1-a --command="sudo tail -f /var/log/cassandra/system.log"
```
