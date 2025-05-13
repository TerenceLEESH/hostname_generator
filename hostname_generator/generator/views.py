import csv
import os
import random
import string
import json
from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from .forms import InitialForm, EsxiHostnameForm

def index(request):
    """Initial view with form to enter how many hostnames to generate"""
    initial_form = InitialForm()
    hostname_form = EsxiHostnameForm()
    
    # Create datastore.csv if it doesn't exist
    datastore_path = os.path.join(settings.DATA_DIR, 'datastore.csv')
    if not os.path.exists(datastore_path):
        with open(datastore_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['hostname'])  # Header row
    
    # Create datacenters.csv if it doesn't exist
    datacenters_path = os.path.join(settings.DATA_DIR, 'datacenters.csv')
    if not os.path.exists(datacenters_path):
        with open(datacenters_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['DC', 'site_code'])  # Header row
            writer.writerow(['Datacenter 1', 'dc1'])
            writer.writerow(['Datacenter 2', 'dc2'])
            writer.writerow(['Datacenter 3', 'dc3'])
    
    return render(request, 'generator/index.html', {
        'initial_form': initial_form,
        'hostname_form': hostname_form,
    })

def generate_hostname(request):
    """Generate hostname based on form inputs"""
    if request.method == 'POST':
        data = json.loads(request.body)
        
        # Create hostname based on form data
        is_dmz = data.get('is_dmz')
        datacenter = data.get('datacenter')
        hardware_type = data.get('hardware_type')
        zone_type = data.get('zone_type')
        custom_zone = data.get('custom_zone')
        
        hostname = ""
        
        # If host is in DMZ
        if is_dmz == 'yes':
            hostname = "e111fdsqqq"
            # Add 4 random characters
            hostname += ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        
        # If host is not in DMZ
        else:
            # Add hardware type prefix
            if hardware_type == 'dell':
                hostname = "d"
            elif hardware_type == 'hp':
                hostname = "h"
            else:
                return JsonResponse({'error': 'Invalid hardware type'}, status=400)
            
            # Add datacenter code
            hostname += datacenter
            
            # Add zone
            if zone_type == 'zone_c':
                hostname += "ppp"
            elif zone_type in ['zone_a', 'zone_b']:
                if not custom_zone:
                    return JsonResponse({'error': 'Custom zone value is required'}, status=400)
                hostname += custom_zone
            else:
                return JsonResponse({'error': 'Invalid zone type'}, status=400)
            
            # Add 3 random characters
            hostname += ''.join(random.choices(string.ascii_lowercase + string.digits, k=3))
        
        # Check if hostname exists in datastore.csv
        datastore_path = os.path.join(settings.DATA_DIR, 'datastore.csv')
        existing_hostnames = []
        
        with open(datastore_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_hostnames.append(row['hostname'])
        
        # If hostname exists, generate a new one
        attempts = 0
        original_hostname = hostname
        while hostname in existing_hostnames and attempts < 10:
            # Add more random characters until we find a unique hostname
            if is_dmz == 'yes':
                hostname = original_hostname[:-4] + ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
            else:
                hostname = original_hostname[:-3] + ''.join(random.choices(string.ascii_lowercase + string.digits, k=3))
            attempts += 1
        
        # If still not unique after multiple attempts, return error
        if hostname in existing_hostnames:
            return JsonResponse({'error': 'Could not generate a unique hostname after multiple attempts'}, status=400)
        
        # Add domain suffix
        full_hostname = hostname + ".abc.abc.abc.com"
        
        return JsonResponse({'hostname': hostname, 'full_hostname': full_hostname})
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)

def check_hostname(request):
    """Check if hostname exists and save it to datastore if it doesn't"""
    if request.method == 'POST':
        data = json.loads(request.body)
        hostname = data.get('hostname')
        
        if not hostname:
            return JsonResponse({'error': 'No hostname provided'}, status=400)
        
        # Check if hostname exists in datastore.csv
        datastore_path = os.path.join(settings.DATA_DIR, 'datastore.csv')
        existing_hostnames = []
        
        with open(datastore_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_hostnames.append(row['hostname'])
        
        if hostname in existing_hostnames:
            return JsonResponse({'exists': True})
        
        # Save hostname to datastore.csv
        with open(datastore_path, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([hostname])
        
        return JsonResponse({'exists': False})
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)