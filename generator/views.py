from django.shortcuts import render, redirect
from django.http import JsonResponse
import csv
import os
import re
from django.views.decorators.csrf import csrf_protect
from django.conf import settings
from .forms import HostnameQuestionnaireForm
from .models import Hostname
import logging
from datetime import datetime

# Mock datacenter data (in real code, you'd load this from a CSV)
DATACENTERS = [
    {'datacenter': 'NYC', 'sitecode': 'NY01'},
    {'datacenter': 'SFO', 'sitecode': 'SF01'},
    {'datacenter': 'CHI', 'sitecode': 'CH01'},
    {'datacenter': 'DAL', 'sitecode': 'DL01'},
    {'datacenter': 'MIA', 'sitecode': 'MI01'},
    {'datacenter': 'LON', 'sitecode': 'LO01'},
    {'datacenter': 'PAR', 'sitecode': 'PA01'},
    {'datacenter': 'SYD', 'sitecode': 'SY01'},
    {'datacenter': 'TOK', 'sitecode': 'TK01'},
]

def load_datacenters_from_csv():
    """Load datacenter information from CSV file"""
    datacenters = []
    csv_path = os.path.join(os.path.dirname(__file__), 'datacenters.csv')
    
    try:
        with open(csv_path, mode='r') as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                datacenters.append(row)
    except FileNotFoundError:
        # If file not found, use the mock data
        datacenters = DATACENTERS
        
    return datacenters

def generate_sequential_hostname(request):
    """
    Generate sequential hostnames based on a prefix pattern
    If abc001 exists, generate abc002 and so on
    """
    if request.method == 'POST':
        base_hostname = request.POST.get('base_hostname', '')
        is_dmz = request.POST.get('is_dmz', 'False') == 'True'
        count = int(request.POST.get('count', 1))
        
        if not base_hostname:
            return JsonResponse({'success': False, 'error': 'Base hostname is required'})
        
        try:
            # Find the next available sequence number
            next_seq = find_next_available_sequence(base_hostname, is_dmz)
            
            # Generate the requested number of hostnames
            hostnames = []
            
            # Format differs between DMZ (3 digits) and non-DMZ (4 digits)
            for i in range(count):
                if is_dmz:
                    hostnames.append(f"{base_hostname}{(next_seq + i):03d}")
                else:
                    hostnames.append(f"{base_hostname}{(next_seq + i):04d}")
            
            return JsonResponse({
                'success': True,
                'hostnames': hostnames,
                'next_sequence': next_seq
            })
            
        except Exception as e:
            import traceback
            return JsonResponse({
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    })

def generate_hostnames(data, datacenters):
    """Generate hostnames based on form data"""
    hostnames = []
    
    # Get the count of hostnames to generate
    count = int(data.get('hostname_count', 1))
    
    # Get the datacenter code
    datacenter_name = data.get('datacenter', '')
    datacenter_code = next((dc['sitecode'] for dc in datacenters if dc['datacenter'] == datacenter_name), 'DC')
    
    # Check if it's a DMZ host
    is_dmz = data.get('is_dmz') == 'True'
    
    if is_dmz:
        # For DMZ hosts, use v{sitecode}u111swea format with 3-digit sequence
        hostname_prefix = f"v{datacenter_code.lower()}u111swea"
        
        # Find the next available number for this hostname pattern (3 digits for DMZ)
        next_number = find_next_available_sequence(hostname_prefix, is_dmz)
        
        # Generate hostnames with 3-digit sequence
        for i in range(count):
            hostname = f"{hostname_prefix}{(next_number + i):03d}"
            hostnames.append(hostname)
    else:
        # For non-DMZ hosts: l-v{sitecode}{hardwaretype}{component3}{component4}{4 digits}
        
        # Get hardware type code (1 character)
        hardware_code = get_hardware_type_code(data.get('hardware_type', ''))
        
        # Get cloud code
        cloud_code = data.get('cloud_code', '').lower()
        if cloud_code == 'custom':
            cloud_code = data.get('custom_cloud_code', '').lower()
        if len(cloud_code) > 3:  # Limit to 3 chars max
            cloud_code = cloud_code[:3]
        
        # Get zone type 
        zone_type = data.get('zone_type', '').lower()
        if len(zone_type) > 3:  # Limit to 3 chars max
            zone_type = zone_type[:3]
        
        # Build the hostname prefix
        hostname_prefix = f"l-v{datacenter_code.lower()}{hardware_code}{cloud_code}{zone_type}"
        
        # Find the next available number for this hostname pattern (4 digits for non-DMZ)
        next_number = find_next_available_sequence(hostname_prefix, is_dmz)
        
        # Generate hostnames with 4-digit sequence
        for i in range(count):
            hostname = f"{hostname_prefix}{(next_number + i):04d}"
            hostnames.append(hostname)
    
    # Save the generated hostnames to CSV
    save_hostnames_to_csv(hostnames, data.get('datacenter', ''), clustername=None)
    
    return hostnames

def generate_clustername(data, datacenters):
    """Generate cluster name based on form data"""
    # Only generate cluster name if not using existing cluster
    if data.get('existing_cluster') == 'True':
        return None
    
    # Get the datacenter code
    datacenter_name = data.get('datacenter', '')
    datacenter_code = next((dc['sitecode'] for dc in datacenters if dc['datacenter'] == datacenter_name), 'DC')
    
    # Prefix for cluster names
    prefix = 'CLS'
    
    # Components for cluster name
    cloud_code = data.get('cloud_code', '')
    zone_type = data.get('zone_type', '')
    
    # Architecture and zone (only relevant for non-existing clusters)
    architecture = data.get('service_architecture', '')
    zone = data.get('zone', '')
    
    # Cluster purpose code (PR=Production, DR=Disaster Recovery, HA=High Availability, VD=Development)
    # Determine based on inputs or default to production
    if data.get('is_dmz') == 'True':
        cluster_purpose = 'HA'  # DMZ clusters are often for high availability
    else:
        # You could add more logic here to determine cluster purpose
        cluster_purpose = 'PR'  # Default to production
    
    # Generate sequential number (in a real app, you'd need to track the latest used)
    purpose_count = 1
    
    # Create the clustername
    clustername = f"{prefix}-{cloud_code}-{zone_type}-{architecture}-{zone}-{datacenter_code}-{cluster_purpose}{purpose_count:02d}"
    
    return clustername

def esxi_hostname_generator(request):
    """View function for the ESXi hostname generator page"""
    # Load datacenters for Q5
    datacenters = load_datacenters_from_csv()
    
    # Initialize form with datacenters
    form = HostnameQuestionnaireForm(request.POST or None, datacenters=datacenters)
    
    # Get current step from session or default to 1
    current_step = request.session.get('current_step', 1)
    total_steps = 9  # Total number of questions
    
    # Handle step navigation
    if request.method == 'POST':
        if 'next_step' in request.POST and current_step < total_steps:
            # Save current step data to session
            request.session[f'step_{current_step}_data'] = request.POST.dict()
            
            # Special handling for custom cloud code (if on step 8)
            if current_step == 8:
                if request.POST.get('cloud_code') == 'custom':
                    custom_code = request.POST.get('custom_cloud_code')
                    if custom_code:
                        # Update the session data to use the custom value directly
                        data = request.session[f'step_{current_step}_data']
                        data['cloud_code'] = custom_code
                        request.session[f'step_{current_step}_data'] = data
                # Handle tg# format for HP hardware
                elif request.POST.get('cloud_code') == 'tg' and request.POST.get('tg_number'):
                    tg_value = f"tg{request.POST.get('tg_number')}"
                    data = request.session[f'step_{current_step}_data']
                    data['cloud_code'] = tg_value
                    request.session[f'step_{current_step}_data'] = data
            
            # Standard next step
            current_step += 1
                
            request.session['current_step'] = current_step
            
            # Calculate steps to display (for progress indicator)
            steps_to_display = calculate_steps_to_display(request.session)
            
            return render(request, 'generator/esxi_hostname.html', {
                'form': form,
                'current_step': current_step,
                'total_steps': total_steps,
                'steps_to_display': steps_to_display,
                'prev_data': {k: request.session.get(f'step_{k}_data', {}) for k in range(1, current_step + 1)},
                'datacenters': datacenters,
            })
            
        elif 'prev_step' in request.POST and current_step > 1:
            # Move to previous step (with special handling for skipped steps)
            if current_step == 4 and request.session.get('step_1_data', {}).get('existing_cluster') == 'True':
                current_step = 1  # Jump back to step 1 from step 4 if steps were skipped
            else:
                current_step -= 1
                
            request.session['current_step'] = current_step
            
            # Calculate steps to display (for progress indicator)
            steps_to_display = calculate_steps_to_display(request.session)
            
            return render(request, 'generator/esxi_hostname.html', {
                'form': form,
                'current_step': current_step,
                'total_steps': total_steps,
                'steps_to_display': steps_to_display,
                'prev_data': {k: request.session.get(f'step_{k}_data', {}) for k in range(1, current_step + 1)},
                'datacenters': datacenters,
            })
            
        elif 'submit' in request.POST or (current_step == 6 and request.POST.get('is_dmz') == 'True'):
            # Save final step data
            request.session[f'step_{current_step}_data'] = request.POST.dict()
            
            # Combine all step data
            all_data = {}
            for step in range(1, total_steps + 1):
                step_data = request.session.get(f'step_{step}_data', {})
                all_data.update(step_data)
            
            # Support for sequence validation
            if 'validate_sequence' in request.POST:
                base_hostname = request.POST.get('base_hostname', '')
                if base_hostname:
                    all_data['base_hostname'] = base_hostname
                
            # Remove navigation keys
            for key in ['next_step', 'prev_step', 'submit', 'csrfmiddlewaretoken', 'validate_sequence']:
                if key in all_data:
                    del all_data[key]
            
            # Generate hostnames based on collected data
            hostnames = generate_hostnames(all_data, datacenters)
            
            # Generate cluster name if needed
            clustername = None
            if all_data.get('existing_cluster') == 'False':
                clustername = generate_clustername(all_data, datacenters)
                
                # Check if cluster name already exists - now only checks, doesn't save
                if clustername and Hostname.validate_clustername_exists(clustername):
                    # Calculate steps to display (for progress indicator)
                    steps_to_display = calculate_steps_to_display(request.session)
                    
                    return render(request, 'generator/esxi_hostname.html', {
                        'form': form,
                        'current_step': current_step,
                        'total_steps': total_steps,
                        'steps_to_display': steps_to_display,
                        'error': f"Cluster name '{clustername}' already exists in the database.",
                        'prev_data': {k: request.session.get(f'step_{k}_data', {}) for k in range(1, current_step + 1)},
                        'datacenters': datacenters,
                    })
            
            # Check if hostnames already exist - now only checks, doesn't save
            existing_hostnames = []
            for hostname in hostnames:
                if Hostname.validate_hostname_exists(hostname):
                    existing_hostnames.append(hostname)
            
            if existing_hostnames:
                # Calculate steps to display (for progress indicator)
                steps_to_display = calculate_steps_to_display(request.session)
                
                return render(request, 'generator/esxi_hostname.html', {
                    'form': form,
                    'current_step': current_step,
                    'total_steps': total_steps,
                    'steps_to_display': steps_to_display,
                    'error': f"These hostnames already exist: {', '.join(existing_hostnames)}",
                    'prev_data': {k: request.session.get(f'step_{k}_data', {}) for k in range(1, current_step + 1)},
                    'datacenters': datacenters,
                })
            
            # REMOVED: Save the hostnames and cluster name to database
            # Instead, just pass the generated names to the result template
            saved_hostnames = hostnames  # No actual saving happens now
            
            # Clear session data
            for step in range(1, total_steps + 1):
                if f'step_{step}_data' in request.session:
                    del request.session[f'step_{step}_data']
            if 'current_step' in request.session:
                del request.session['current_step']
            
            return render(request, 'generator/result.html', {
                'hostnames': saved_hostnames,
                'hostname_count': len(saved_hostnames),
                'clustername': clustername,
                'is_dmz': all_data.get('is_dmz') == 'True',  # Pass DMZ status
                'preview_only': True  # New flag indicating no database save happened
            })
    
    # Initial GET request
    if request.method == 'GET':
        # Reset form progress
        current_step = 1
        request.session['current_step'] = current_step
        for step in range(1, total_steps + 1):
            if f'step_{step}_data' in request.session:
                del request.session[f'step_{step}_data']
    
    # Calculate steps to display (for progress indicator)
    steps_to_display = calculate_steps_to_display(request.session)
    
    return render(request, 'generator/esxi_hostname.html', {
        'form': form,
        'current_step': current_step,
        'total_steps': total_steps,
        'steps_to_display': steps_to_display,
        'prev_data': {k: request.session.get(f'step_{k}_data', {}) for k in range(1, current_step)},
        'datacenters': datacenters,
    })

def calculate_steps_to_display(session):
    """Calculate which steps should be displayed in the progress indicator"""
    steps = list(range(1, 10))  # All steps by default
    
    # If using existing cluster, skip steps 2-3
    if session.get('step_1_data', {}).get('existing_cluster') == 'True':
        steps = [1, 4, 5, 6, 7, 8, 9]
        
    return steps

def validate_hostname_ajax(request):
    """AJAX endpoint to check if hostname exists"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        hostname = request.POST.get('hostname', '')
        exists = Hostname.validate_hostname_exists(hostname)
        return JsonResponse({'exists': exists})
    return JsonResponse({'error': 'Invalid request'}, status=400)

@csrf_protect
def check_existing_hostnames(request):
    """Check existing hostnames in CSV and return the next available sequence number"""
    if request.method == 'POST':
        base_hostname = request.POST.get('base_hostname', '')
        is_dmz = request.POST.get('is_dmz', 'False') == 'True'
        
        try:
            # Print debug information
            print(f"Checking for hostname: {base_hostname}, DMZ: {is_dmz}")
            
            # Find next available sequence
            next_seq = find_next_available_sequence(base_hostname, is_dmz)
            print(f"Found next sequence number: {next_seq}")
            
            return JsonResponse({
                'success': True,
                'next_sequence': next_seq
            })
            
        except Exception as e:
            import traceback
            print(f"Error in check_existing_hostnames: {e}")
            print(traceback.format_exc())
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    })

def index(request):
    """Alias for the esxi_hostname_generator view"""
    return esxi_hostname_generator(request)

def get_hardware_type_code(hardware_type):
    """Convert full hardware type to single character code"""
    hardware_map = {
        'Dell': 'd',
        'HP': 'h'
    }
    return hardware_map.get(hardware_type, 'x')  # Default to 'x' if unknown

def esxi_hostname(request):
    """Alias for the esxi_hostname_generator view"""
    return esxi_hostname_generator(request)

def find_next_available_sequence(hostname_prefix, is_dmz=False):
    """Find the next available sequence number for a hostname prefix"""
    # Get all existing hostnames that match the prefix
    existing_hostnames = get_existing_hostnames()
    
    # Filter hostnames that match the prefix
    matching_hostnames = []
    pattern = re.escape(hostname_prefix) + r'(\d+)$'
    
    for hostname in existing_hostnames:
        match = re.search(pattern, hostname)
        if match:
            seq_num = int(match.group(1))
            matching_hostnames.append(seq_num)
    
    # If no matching hostnames found, start from 1
    if not matching_hostnames:
        return 1
        
    # Sort sequence numbers
    matching_hostnames.sort()
    
    # Find the first gap in the sequence
    for i in range(len(matching_hostnames)):
        if i == 0 and matching_hostnames[0] > 1:
            # First number is greater than 1, so use 1
            return 1
            
        if i < len(matching_hostnames) - 1:
            curr = matching_hostnames[i]
            next_val = matching_hostnames[i + 1]
            
            if next_val > curr + 1:
                # Found a gap, return the next number in sequence
                return curr + 1
    
    # No gaps found, use next available number
    return matching_hostnames[-1] + 1

def get_existing_hostnames():
    """Get all existing hostnames from the CSV file"""
    hostnames = []
    csv_path = os.path.join(settings.BASE_DIR, 'generator', 'data', 'hostnames.csv')
    
    if not os.path.exists(os.path.dirname(csv_path)):
        os.makedirs(os.path.dirname(csv_path))
        
    if not os.path.exists(csv_path):
        # Create the CSV file with header if it doesn't exist
        with open(csv_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['hostname', 'datacenter', 'cluster_name', 'created_date'])
    else:
        # Read existing hostnames
        try:
            with open(csv_path, 'r') as csvfile:
                reader = csv.reader(csvfile)
                next(reader, None)  # Skip header row
                
                for row in reader:
                    if row and len(row) > 0:
                        hostnames.append(row[0].strip())  # First column contains hostname
        except Exception as e:
            print(f"Error reading CSV: {e}")
    
    return hostnames

def save_hostnames_to_csv(hostnames, datacenter, clustername=None):
    """Save generated hostnames to CSV file"""
    from datetime import datetime
    
    csv_path = os.path.join(settings.BASE_DIR, 'generator', 'data', 'hostnames.csv')
    
    # Ensure the directory exists
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    
    # Read existing content first to avoid overwriting
    existing_hostnames = []
    try:
        if os.path.exists(csv_path):
            with open(csv_path, 'r') as csvfile:
                reader = csv.reader(csvfile)
                existing_hostnames = list(reader)
        else:
            # Create with header
            existing_hostnames = [['hostname', 'datacenter', 'cluster_name', 'created_date']]
    except Exception as e:
        print(f"Error reading CSV: {e}")
        existing_hostnames = [['hostname', 'datacenter', 'cluster_name', 'created_date']]
    
    # Check if any of the hostnames already exist
    existing_hostnames_list = [row[0] for row in existing_hostnames[1:] if row]
    
    # Open file for writing
    try:
        with open(csv_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            # Write header and existing entries
            writer.writerows(existing_hostnames)
            
            # Add new hostnames
            date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for hostname in hostnames:
                if hostname not in existing_hostnames_list:
                    writer.writerow([hostname, datacenter, clustername or "", date_str])
    except Exception as e:
        print(f"Error writing to CSV: {e}")
    
    return True

def get_next_hostname_sequence(base_hostname, is_dmz):
    """Helper function to get the next available sequence number"""
    return find_next_available_sequence(base_hostname, is_dmz)

def validate_hostname_exists(hostname):
    """Check if hostname already exists in CSV"""
    existing_hostnames = get_existing_hostnames()
    return hostname in existing_hostnames

def debug_log(message):
    """Write a debug message to a log file"""
    log_path = os.path.join(settings.BASE_DIR, 'generator', 'data', 'debug_log.txt')
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, 'a') as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        print(f"Error writing to debug log: {e}")