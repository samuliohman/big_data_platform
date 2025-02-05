Commands to run on a google SDK CLI (local powershell instance):
```
gcloud init
gcloud auth application-default login
```

```
terraform init
terraform apply

# Configure cassandra using powershell script
.\configure_cassandra.ps1

terraform destroy
```

When cassandra VMs are properly running, here are the commands for data ingestion.
```
cd data_ingestion
py -m pip install -r requirements.txt

# Get and use nodes' external IPs
$NORDICS_EXT_IP = gcloud compute instances describe nordics-node --zone=europe-north1-a --format="get(networkInterfaces[0].accessConfigs[0].natIP)"
$WEST_EXT_IP = gcloud compute instances describe eu-west-node --zone=europe-west1-b --format="get(networkInterfaces[0].accessConfigs[0].natIP)"

py data_ingestion.py --nodes "$NORDICS_EXT_IP" "$WEST_EXT_IP"
```



Additional helper scripts for debugging:
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