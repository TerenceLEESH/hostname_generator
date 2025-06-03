from django.db import models
import pandas as pd
import os
import datetime

# Mock data for existing hostnames
EXISTING_HOSTNAMES = [
    "ESXI-Dell-QQA-AAA-OSA-A-NY01-01",
    "ESXI-Dell-QQA-AAA-OSA-A-NY01-02",
    "ESXI-Dell-QQA-AAA-OSA-B-NY01-01",
    "ESXI-HP-QQB-BBB-ESA-C-SF01-01",
    "ESXI-HP-QQB-BBB-ESA-C-SF01-02",
    "ESXI-HP-QQB-BBB-ESA-D-SF01-01",
    "ESXI-DMZ-QQA-CCC-CH01-01",
    "ESXI-DMZ-QQA-CCC-CH01-02",
    "ESXI-Dell-QQC-AAA-OSA-E-DL01-01",
    "ESXI-Dell-QQC-AAA-OSA-E-DL01-02",
    "ESXI-HP-QQC-BBB-ESA-A-MI01-01",
    "ESXI-HP-QQC-BBB-ESA-A-MI01-02",
    "ESXI-Dell-QQA-CCC-OSA-B-LO01-01",
    "ESXI-Dell-QQA-CCC-OSA-B-LO01-02",
    "ESXI-HP-QQB-AAA-ESA-C-PA01-01",
    "ESXI-HP-QQB-AAA-ESA-C-PA01-02",
    "ESXI-DMZ-QQC-BBB-SY01-01",
    "ESXI-DMZ-QQC-BBB-SY01-02",
    "ESXI-Dell-QQA-CCC-OSA-D-TK01-01",
    "ESXI-Dell-QQA-CCC-OSA-D-TK01-02",
    "ESXI-HP-QQB-AAA-ESA-E-NY01-03",
    "ESXI-HP-QQB-AAA-ESA-E-NY01-04",
    "ESXI-Dell-QQC-BBB-OSA-A-SF01-03",
    "ESXI-Dell-QQC-BBB-OSA-A-SF01-04",
    "ESXI-HP-QQA-CCC-ESA-B-CH01-03",
    "ESXI-HP-QQA-CCC-ESA-B-CH01-04",
    "ESXI-DMZ-QQB-AAA-DL01-03",
    "ESXI-DMZ-QQB-AAA-DL01-04",
    "ESXI-Dell-QQC-BBB-OSA-C-MI01-03",
    "ESXI-Dell-QQC-BBB-OSA-C-MI01-04",
    "ESXI-HP-QQA-CCC-ESA-D-LO01-03",
    "ESXI-HP-QQA-CCC-ESA-D-LO01-04",
    "ESXI-Dell-QQB-AAA-OSA-E-PA01-03",
    "ESXI-Dell-QQB-AAA-OSA-E-PA01-04",
    "ESXI-HP-QQC-BBB-ESA-A-SY01-03",
    "ESXI-HP-QQC-BBB-ESA-A-SY01-04",
    "ESXI-DMZ-QQA-CCC-TK01-03",
    "ESXI-DMZ-QQA-CCC-TK01-04",
    "ESXI-Dell-QQB-AAA-OSA-B-NY01-05",
    "ESXI-Dell-QQB-AAA-OSA-B-NY01-06",
    "ESXI-HP-QQC-BBB-ESA-C-SF01-05",
    "ESXI-HP-QQC-BBB-ESA-C-SF01-06",
    "ESXI-Dell-QQA-CCC-OSA-D-CH01-05",
    "ESXI-Dell-QQA-CCC-OSA-D-CH01-06",
    "ESXI-HP-QQB-AAA-ESA-E-DL01-05",
    "ESXI-HP-QQB-AAA-ESA-E-DL01-06",
    "ESXI-DMZ-QQC-BBB-MI01-05",
    "ESXI-DMZ-QQC-BBB-MI01-06",
    "ESXI-Dell-QQA-CCC-OSA-A-LO01-05",
    "ESXI-Dell-QQA-CCC-OSA-A-LO01-06"
]

class HostnameManager:
    """Class for managing hostnames using pandas DataFrame instead of Django models"""
    _existing_hostname_df = None
    _existing_cluster_df = None
    
    @classmethod
    def get_existing_hostnames_df(cls):
        """Get or create the DataFrame of existing hostnames"""
        if cls._existing_hostname_df is None:
            # Attempt to load from CSV file if it exists
            csv_path = os.path.join(os.path.dirname(__file__), 'existing_hostnames.csv')
            try:
                cls._existing_hostname_df = pd.read_csv(csv_path)
            except (FileNotFoundError, pd.errors.EmptyDataError):
                # Create DataFrame from mock data if file doesn't exist
                cls._existing_hostname_df = pd.DataFrame({
                    'hostname': EXISTING_HOSTNAMES,
                    'created_at': [datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')] * len(EXISTING_HOSTNAMES)
                })
                # Save to CSV for persistence
                cls._existing_hostname_df.to_csv(csv_path, index=False)
        
        return cls._existing_hostname_df
    
    @classmethod
    def get_existing_clusters_df(cls):
        """Get or create the DataFrame of existing cluster names"""
        if cls._existing_cluster_df is None:
            # Attempt to load from CSV file if it exists
            csv_path = os.path.join(os.path.dirname(__file__), 'existing_clusternames.csv')
            try:
                cls._existing_cluster_df = pd.read_csv(csv_path)
            except (FileNotFoundError, pd.errors.EmptyDataError):
                # Create empty DataFrame if file doesn't exist
                cls._existing_cluster_df = pd.DataFrame({
                    'clustername': [],
                    'created_at': []
                })
                # Save to CSV for persistence
                cls._existing_cluster_df.to_csv(csv_path, index=False)
        
        return cls._existing_cluster_df
    
    @classmethod
    def validate_hostname_exists(cls, hostname):
        """Check if hostname already exists in the DataFrame"""
        df = cls.get_existing_hostnames_df()
        return hostname in df['hostname'].values
    
    @classmethod
    def validate_clustername_exists(cls, clustername):
        """Check if cluster name already exists in the DataFrame"""
        df = cls.get_existing_clusters_df()
        return clustername in df['clustername'].values
    
    @classmethod
    def add_hostname(cls, hostname):
        """Add a new hostname to the DataFrame and save to CSV"""
        df = cls.get_existing_hostnames_df()
        new_row = pd.DataFrame({
            'hostname': [hostname],
            'created_at': [datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
        })
        cls._existing_hostname_df = pd.concat([df, new_row], ignore_index=True)
        
        # Save updated DataFrame to CSV
        csv_path = os.path.join(os.path.dirname(__file__), 'existing_hostnames.csv')
        cls._existing_hostname_df.to_csv(csv_path, index=False)
        return True
    
    @classmethod
    def add_clustername(cls, clustername):
        """Add a new cluster name to the DataFrame and save to CSV"""
        df = cls.get_existing_clusters_df()
        new_row = pd.DataFrame({
            'clustername': [clustername],
            'created_at': [datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
        })
        cls._existing_cluster_df = pd.concat([df, new_row], ignore_index=True)
        
        # Save updated DataFrame to CSV
        csv_path = os.path.join(os.path.dirname(__file__), 'existing_clusternames.csv')
        cls._existing_cluster_df.to_csv(csv_path, index=False)
        return True

class Hostname(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    @classmethod
    def validate_hostname_exists(cls, hostname):
        """Delegate to HostnameManager"""
        return HostnameManager.validate_hostname_exists(hostname)
    
    @classmethod
    def validate_clustername_exists(cls, clustername):
        """Delegate to HostnameManager"""
        return HostnameManager.validate_clustername_exists(clustername)
    
    @classmethod
    def add_hostname_to_df(cls, hostname):
        """Delegate to HostnameManager"""
        return HostnameManager.add_hostname(hostname)
    
    @classmethod
    def add_clustername_to_df(cls, clustername):
        """Delegate to HostnameManager"""
        return HostnameManager.add_clustername(clustername)