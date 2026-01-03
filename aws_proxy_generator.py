#!/usr/bin/env python3
"""
AWS Proxy Generator

This script manages AWS EC2 instances as HTTP/SOCKS proxies.
It can create instances, set up proxies, renew IPs, and manage the proxy infrastructure.
"""

import boto3
import time
import argparse
import json
import sys
from typing import List, Dict, Optional
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AWSProxyGenerator:
    """
    Manages AWS EC2 instances configured as HTTP/SOCKS proxies.
    """

    def __init__(self, region: str = 'us-east-1', profile: Optional[str] = None):
        """
        Initialize the AWS Proxy Generator.

        Args:
            region: AWS region to use
            profile: AWS profile name (optional)
        """
        session_kwargs = {'region_name': region}
        if profile:
            session_kwargs['profile_name'] = profile

        self.session = boto3.Session(**session_kwargs)
        self.ec2_client = self.session.client('ec2')
        self.ec2_resource = self.session.resource('ec2')
        self.region = region

    def create_security_group(self, group_name: str = 'proxy-security-group') -> str:
        """
        Create a security group for proxy instances.

        Args:
            group_name: Name for the security group

        Returns:
            Security group ID
        """
        try:
            # Check if security group already exists
            response = self.ec2_client.describe_security_groups(
                Filters=[{'Name': 'group-name', 'Values': [group_name]}]
            )
            
            if response['SecurityGroups']:
                sg_id = response['SecurityGroups'][0]['GroupId']
                logger.info(f"Security group '{group_name}' already exists: {sg_id}")
                return sg_id

            # Create new security group
            response = self.ec2_client.create_security_group(
                GroupName=group_name,
                Description='Security group for proxy instances'
            )
            sg_id = response['GroupId']
            logger.info(f"Created security group: {sg_id}")

            # Add ingress rules
            self.ec2_client.authorize_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=[
                    {
                        'IpProtocol': 'tcp',
                        'FromPort': 22,
                        'ToPort': 22,
                        'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                    },
                    {
                        'IpProtocol': 'tcp',
                        'FromPort': 3128,
                        'ToPort': 3128,
                        'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                    },
                    {
                        'IpProtocol': 'tcp',
                        'FromPort': 1080,
                        'ToPort': 1080,
                        'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                    }
                ]
            )
            logger.info("Added ingress rules to security group")

            return sg_id

        except Exception as e:
            logger.error(f"Error creating security group: {e}")
            raise

    def get_user_data_script(self) -> str:
        """
        Generate user data script for proxy setup.

        Returns:
            User data script as string
        """
        return """#!/bin/bash
set -e

# Update system
yum update -y

# Install Squid (HTTP proxy)
yum install -y squid

# Configure Squid
cat > /etc/squid/squid.conf <<'EOF'
http_port 3128
acl localnet src 0.0.0.0/0
http_access allow localnet
http_access allow localhost
http_access deny all
coredump_dir /var/spool/squid
refresh_pattern ^ftp: 1440 20% 10080
refresh_pattern ^gopher: 1440 0% 1440
refresh_pattern -i (/cgi-bin/|\?) 0 0% 0
refresh_pattern . 0 20% 4320
EOF

# Start and enable Squid
systemctl start squid
systemctl enable squid

# Install Dante (SOCKS proxy)
yum install -y gcc make pam-devel
cd /tmp
wget https://www.inet.no/dante/files/dante-1.4.3.tar.gz
tar xzf dante-1.4.3.tar.gz
cd dante-1.4.3
./configure
make
make install

# Configure Dante
cat > /etc/sockd.conf <<'EOF'
logoutput: /var/log/sockd.log
internal: 0.0.0.0 port = 1080
external: eth0
clientmethod: none
socksmethod: none
user.privileged: root
user.unprivileged: nobody

client pass {
    from: 0.0.0.0/0 to: 0.0.0.0/0
    log: error connect disconnect
}

socks pass {
    from: 0.0.0.0/0 to: 0.0.0.0/0
    log: error connect disconnect
}
EOF

# Create systemd service for Dante
cat > /etc/systemd/system/sockd.service <<'EOF'
[Unit]
Description=Dante SOCKS Server
After=network.target

[Service]
Type=forking
PIDFile=/var/run/sockd.pid
ExecStart=/usr/local/sbin/sockd -D
ExecReload=/bin/kill -HUP $MAINPID
KillMode=process
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# Start and enable Dante
systemctl daemon-reload
systemctl start sockd
systemctl enable sockd

logger "Proxy setup completed successfully"
"""

    def create_instances(
        self,
        count: int = 1,
        instance_type: str = 't2.micro',
        key_name: Optional[str] = None
    ) -> List[Dict]:
        """
        Create EC2 instances configured as proxies.

        Args:
            count: Number of instances to create
            instance_type: EC2 instance type
            key_name: SSH key pair name (optional)

        Returns:
            List of instance information dictionaries
        """
        try:
            # Create security group
            sg_id = self.create_security_group()

            # Get latest Amazon Linux 2 AMI
            response = self.ec2_client.describe_images(
                Owners=['amazon'],
                Filters=[
                    {'Name': 'name', 'Values': ['amzn2-ami-hvm-*-x86_64-gp2']},
                    {'Name': 'state', 'Values': ['available']}
                ],
                MaxResults=1
            )
            ami_id = response['Images'][0]['ImageId']
            logger.info(f"Using AMI: {ami_id}")

            # Prepare instance parameters
            instance_params = {
                'ImageId': ami_id,
                'InstanceType': instance_type,
                'MinCount': count,
                'MaxCount': count,
                'SecurityGroupIds': [sg_id],
                'UserData': self.get_user_data_script(),
                'TagSpecifications': [
                    {
                        'ResourceType': 'instance',
                        'Tags': [
                            {'Key': 'Name', 'Value': 'proxy-instance'},
                            {'Key': 'Type', 'Value': 'proxy'}
                        ]
                    }
                ]
            }

            if key_name:
                instance_params['KeyName'] = key_name

            # Launch instances
            response = self.ec2_client.run_instances(**instance_params)
            instances = response['Instances']
            instance_ids = [i['InstanceId'] for i in instances]

            logger.info(f"Launched {len(instance_ids)} instances: {instance_ids}")
            logger.info("Waiting for instances to be running...")

            # Wait for instances to be running
            waiter = self.ec2_client.get_waiter('instance_running')
            waiter.wait(InstanceIds=instance_ids)

            # Wait additional time for user data script to complete
            logger.info("Waiting for proxy setup to complete (90 seconds)...")
            time.sleep(90)

            # Get instance details
            instances_info = self.get_instances_info(instance_ids)

            logger.info("Instances created successfully!")
            return instances_info

        except Exception as e:
            logger.error(f"Error creating instances: {e}")
            raise

    def get_instances_info(self, instance_ids: Optional[List[str]] = None) -> List[Dict]:
        """
        Get information about proxy instances.

        Args:
            instance_ids: List of instance IDs (optional, gets all proxy instances if None)

        Returns:
            List of instance information dictionaries
        """
        try:
            filters = [{'Name': 'tag:Type', 'Values': ['proxy']}]
            
            if instance_ids:
                filters.append({'Name': 'instance-id', 'Values': instance_ids})

            response = self.ec2_client.describe_instances(Filters=filters)

            instances_info = []
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    if instance['State']['Name'] == 'running':
                        info = {
                            'instance_id': instance['InstanceId'],
                            'public_ip': instance.get('PublicIpAddress'),
                            'private_ip': instance.get('PrivateIpAddress'),
                            'state': instance['State']['Name'],
                            'type': instance['InstanceType'],
                            'http_proxy': f"http://{instance.get('PublicIpAddress')}:3128" if instance.get('PublicIpAddress') else None,
                            'socks_proxy': f"socks5://{instance.get('PublicIpAddress')}:1080" if instance.get('PublicIpAddress') else None
                        }
                        instances_info.append(info)

            return instances_info

        except Exception as e:
            logger.error(f"Error getting instances info: {e}")
            raise

    def renew_ips(self, instance_ids: Optional[List[str]] = None) -> List[Dict]:
        """
        Renew IP addresses of instances by stopping and starting them.
        This method uses STOP → START to get new public IPs.

        Args:
            instance_ids: List of instance IDs (optional, renews all proxy instances if None)

        Returns:
            List of updated instance information dictionaries
        """
        try:
            # Get instances to renew
            if instance_ids is None:
                filters = [{'Name': 'tag:Type', 'Values': ['proxy']}]
                response = self.ec2_client.describe_instances(Filters=filters)
                instance_ids = []
                for reservation in response['Reservations']:
                    for instance in reservation['Instances']:
                        if instance['State']['Name'] == 'running':
                            instance_ids.append(instance['InstanceId'])

            if not instance_ids:
                logger.warning("No instances found to renew IPs")
                return []

            logger.info(f"Renewing IPs for instances: {instance_ids}")

            # Stop instances
            logger.info("Stopping instances...")
            self.ec2_client.stop_instances(InstanceIds=instance_ids)
            
            # Wait for instances to stop
            waiter = self.ec2_client.get_waiter('instance_stopped')
            waiter.wait(InstanceIds=instance_ids)
            logger.info("Instances stopped successfully")

            # Start instances
            logger.info("Starting instances...")
            self.ec2_client.start_instances(InstanceIds=instance_ids)
            
            # Wait for instances to start
            waiter = self.ec2_client.get_waiter('instance_running')
            waiter.wait(InstanceIds=instance_ids)
            logger.info("Instances started successfully")

            # Wait additional time for services to be ready
            logger.info("Waiting for proxy services to be ready (30 seconds)...")
            time.sleep(30)

            # Get updated instance information
            instances_info = self.get_instances_info(instance_ids)

            logger.info("IP addresses renewed successfully!")
            return instances_info

        except Exception as e:
            logger.error(f"Error renewing IPs: {e}")
            raise

    def terminate_instances(self, instance_ids: Optional[List[str]] = None) -> None:
        """
        Terminate proxy instances.

        Args:
            instance_ids: List of instance IDs (optional, terminates all proxy instances if None)
        """
        try:
            # Get instances to terminate
            if instance_ids is None:
                filters = [{'Name': 'tag:Type', 'Values': ['proxy']}]
                response = self.ec2_client.describe_instances(Filters=filters)
                instance_ids = []
                for reservation in response['Reservations']:
                    for instance in reservation['Instances']:
                        if instance['State']['Name'] != 'terminated':
                            instance_ids.append(instance['InstanceId'])

            if not instance_ids:
                logger.warning("No instances found to terminate")
                return

            logger.info(f"Terminating instances: {instance_ids}")
            self.ec2_client.terminate_instances(InstanceIds=instance_ids)
            logger.info("Instances terminated successfully")

        except Exception as e:
            logger.error(f"Error terminating instances: {e}")
            raise

    def export_proxy_list(self, filename: str = 'proxies.txt', format: str = 'http') -> None:
        """
        Export proxy list to a file.

        Args:
            filename: Output filename
            format: Proxy format ('http' or 'socks')
        """
        try:
            instances = self.get_instances_info()
            
            if not instances:
                logger.warning("No proxy instances found")
                return

            with open(filename, 'w') as f:
                for instance in instances:
                    if format == 'http' and instance['http_proxy']:
                        f.write(f"{instance['http_proxy']}\n")
                    elif format == 'socks' and instance['socks_proxy']:
                        f.write(f"{instance['socks_proxy']}\n")

            logger.info(f"Exported {len(instances)} proxies to {filename}")

        except Exception as e:
            logger.error(f"Error exporting proxy list: {e}")
            raise


def main():
    """
    Main function to handle command-line interface.
    """
    parser = argparse.ArgumentParser(description='AWS Proxy Generator')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--profile', help='AWS profile name')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Create command
    create_parser = subparsers.add_parser('create', help='Create proxy instances')
    create_parser.add_argument('--count', type=int, default=1, help='Number of instances')
    create_parser.add_argument('--type', default='t2.micro', help='Instance type')
    create_parser.add_argument('--key', help='SSH key pair name')

    # List command
    subparsers.add_parser('list', help='List proxy instances')

    # Renew command
    renew_parser = subparsers.add_parser('renew', help='Renew IP addresses')
    renew_parser.add_argument('--instances', nargs='+', help='Instance IDs to renew')

    # Terminate command
    terminate_parser = subparsers.add_parser('terminate', help='Terminate instances')
    terminate_parser.add_argument('--instances', nargs='+', help='Instance IDs to terminate')

    # Export command
    export_parser = subparsers.add_parser('export', help='Export proxy list')
    export_parser.add_argument('--output', default='proxies.txt', help='Output filename')
    export_parser.add_argument('--format', choices=['http', 'socks'], default='http', help='Proxy format')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize generator
    generator = AWSProxyGenerator(region=args.region, profile=args.profile)

    # Execute command
    if args.command == 'create':
        instances = generator.create_instances(
            count=args.count,
            instance_type=args.type,
            key_name=args.key
        )
        print("\n" + "="*50)
        print("CREATED PROXY INSTANCES")
        print("="*50)
        print(json.dumps(instances, indent=2))

    elif args.command == 'list':
        instances = generator.get_instances_info()
        print("\n" + "="*50)
        print("PROXY INSTANCES")
        print("="*50)
        if instances:
            print(json.dumps(instances, indent=2))
        else:
            print("No proxy instances found")

    elif args.command == 'renew':
        instances = generator.renew_ips(instance_ids=args.instances)
        print("\n" + "="*50)
        print("RENEWED IP ADDRESSES")
        print("="*50)
        print(json.dumps(instances, indent=2))

    elif args.command == 'terminate':
        generator.terminate_instances(instance_ids=args.instances)
        print("\nInstances terminated successfully")

    elif args.command == 'export':
        generator.export_proxy_list(filename=args.output, format=args.format)
        print(f"\nProxies exported to {args.output}")


if __name__ == '__main__':
    main()
