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
    # Get all existing hostnames
    existing_hostnames = get_existing_hostnames()
    
    # Get all existing clusternames (to avoid conflicts)
    existing_clusternames = get_existing_clusternames()
    
    # Combine all names
    all_existing_names = existing_hostnames + existing_clusternames
    
    # Filter names that match the prefix
    matching_sequences = []
    pattern = re.escape(hostname_prefix) + r'(\d+)$'
    debug_log(f"Checking pattern: {pattern} against {len(all_existing_names)} names")
    
    for name in all_existing_names:
        match = re.search(pattern, name)
        if match:
            seq_num = int(match.group(1))
            matching_sequences.append(seq_num)
    
    debug_log(f"Found {len(matching_sequences)} matching sequences for prefix {hostname_prefix}")
    
    # If no matching sequences found, start from 1
    if not matching_sequences:
        return 1
    
    # Sort sequence numbers
    matching_sequences.sort()
    
    # Find the first gap in the sequence
    for i in range(len(matching_sequences)):
        if i == 0 and matching_sequences[0] > 1:
            # First number is greater than 1, so use 1
            return 1
        
        if i < len(matching_sequences) - 1:
            curr = matching_sequences[i]
            next_val = matching_sequences[i + 1]
            
            if next_val > curr + 1:
                # Found a gap, return the next number in sequence
                return curr + 1
    
    # No gaps found, use next available number
    return matching_sequences[-1] + 1


def get_existing_hostnames():
    """Get all existing hostnames from the hostname CSV files"""
    hostnames = []
    
    # Check hostnames.csv in data folder
    csv_path = os.path.join(settings.BASE_DIR, 'generator', 'data', 'hostnames.csv')
    
    if not os.path.exists(os.path.dirname(csv_path)):
        os.makedirs(os.path.dirname(csv_path))
        
    if not os.path.exists(csv_path):
        # Create the CSV file with header if it doesn't exist
        with open(csv_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['servername'])
    else:
        # Read existing hostnames
        try:
            with open(csv_path, 'r') as csvfile:
                reader = csv.reader(csvfile)
                next(reader, None)  # Skip header row
                
                for row in reader:
                    if row and len(row) > 0:
                        hostnames.append(row[0].strip())
        except Exception as e:
            debug_log(f"Error reading hostnames CSV: {e}")
    
    return hostnames


def get_existing_clusternames():
    """Get all existing clusternames from the clustername CSV file"""
    clusternames = []
    clusternames_csv_path = os.path.join(settings.BASE_DIR, 'generator', 'existing_clusternames.csv')
    
    try:
        if os.path.exists(clusternames_csv_path):
            with open(clusternames_csv_path, 'r') as csvfile:
                reader = csv.reader(csvfile)
                next(reader, None)  # Skip header row
                for row in reader:
                    if row and len(row) > 0:
                        clusternames.append(row[0].strip())
        else:
            debug_log(f"Clusternames CSV does not exist: {clusternames_csv_path}")
    except Exception as e:
        debug_log(f"Error reading existing_clusternames.csv: {e}")
    
    return clusternames


def save_hostnames_to_csv(hostnames):
    """Save generated hostnames to CSV file with duplicate prevention"""
    import traceback
    
    csv_path = os.path.join(settings.BASE_DIR, 'generator', 'data', 'hostnames.csv')
    
    # Ensure the directory exists
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    
    # Get all existing hostnames
    existing_hostnames = []
    try:
        if os.path.exists(csv_path):
            with open(csv_path, 'r') as csvfile:
                reader = csv.reader(csvfile)
                existing_hostnames = list(reader)
        else:
            # Create with header
            existing_hostnames = [['servername']]
    except Exception as e:
        debug_log(f"Error reading hostnames CSV: {e}")
        existing_hostnames = [['servername']]
    
    # Get all existing hostnames and clusternames for validation
    all_existing_names = get_existing_hostnames() + get_existing_clusternames()
    all_existing_set = {name.lower() for name in all_existing_names}
    
    # Hostnames that will actually be added (duplicates filtered out)
    hostnames_to_add = []
    duplicates = []
    
    # Check each hostname and only add if it doesn't exist
    for hostname in hostnames:
        # Case-insensitive comparison
        if hostname.strip().lower() in all_existing_set:
            duplicates.append(hostname)
            debug_log(f"Duplicate hostname found: {hostname}")
        else:
            hostnames_to_add.append(hostname)
            # Add to the set to prevent duplicates even within the batch
            all_existing_set.add(hostname.strip().lower())
    
    # Log duplicate information
    if duplicates:
        debug_log(f"WARNING: {len(duplicates)} duplicate hostnames were found and will not be added")
        
    # Write non-duplicate hostnames to the CSV
    if hostnames_to_add:
        try:
            with open(csv_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                # Write header
                writer.writerow(['servername'])
                
                # Write existing hostnames (except header)
                for row in existing_hostnames[1:]:
                    if row:  # Skip empty rows
                        writer.writerow(row)
                
                # Add new hostnames
                for hostname in hostnames_to_add:
                    writer.writerow([hostname])
            debug_log(f"Successfully wrote {len(hostnames_to_add)} hostnames to CSV")
        except Exception as e:
            debug_log(f"Error writing to hostnames CSV: {e}")
            print(traceback.format_exc())
            return False
    else:
        debug_log("No new hostnames to add (all were duplicates)")
    
    # Return information about which hostnames were added and which were duplicates
    return {
        'added': hostnames_to_add,
        'duplicates': duplicates,
        'success': len(hostnames_to_add) > 0 or len(duplicates) == 0
    }

def save_clustername_to_csv(clustername):
    """Save a clustername to the clusternames CSV file"""
    clusternames_csv_path = os.path.join(settings.BASE_DIR, 'generator', 'existing_clusternames.csv')
    
    # Ensure the file exists with header
    if not os.path.exists(clusternames_csv_path):
        try:
            with open(clusternames_csv_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['clustername'])
        except Exception as e:
            debug_log(f"Error creating clusternames CSV: {e}")
            return False
    
    # Read existing clusternames
    existing_rows = []
    try:
        with open(clusternames_csv_path, 'r') as csvfile:
            reader = csv.reader(csvfile)
            existing_rows = list(reader)
    except Exception as e:
        debug_log(f"Error reading clusternames CSV: {e}")
        existing_rows = [['clustername']]
    
    # Get all existing names for validation
    all_existing_names = get_existing_hostnames() + get_existing_clusternames()
    all_existing_set = {name.lower() for name in all_existing_names}
    
    # Check if clustername already exists (case-insensitive)
    if clustername.lower() in all_existing_set:
        debug_log(f"Clustername {clustername} already exists")
        return False
    
    # Append the new clustername if it doesn't exist
    try:
        with open(clusternames_csv_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            # Write header
            writer.writerow(['clustername'])
            
            # Write existing clusternames (except header)
            for row in existing_rows[1:]:
                if row:  # Skip empty rows
                    writer.writerow(row)
            
            # Add the new clustername
            writer.writerow([clustername])
        debug_log(f"Successfully added clustername: {clustername}")
        return True
    except Exception as e:
        debug_log(f"Error writing to clusternames CSV: {e}")
        return False

def create_cluster_view(request):
    """View to create a new cluster name"""
    if request.method == 'POST':
        datacenter = request.POST.get('datacenter')
        architecture = request.POST.get('architecture') 
        zone = request.POST.get('zone')
        
        # Generate the clustername
        clustername = generate_clustername(datacenter, architecture, zone)
        
        # Save the clustername
        result = save_clustername_to_csv(clustername)
        
        if result:
            return JsonResponse({
                'success': True,
                'clustername': clustername
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to save clustername or it already exists'
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


def create_hostnames_view(request):
    """View to create new hostnames"""
    if request.method == 'POST':
        # Get the hostnames from the request
        hostnames = request.POST.getlist('hostnames[]')
        
        # Save the hostnames
        result = save_hostnames_to_csv(hostnames)
        
        if isinstance(result, dict) and result.get('success', False):
            return JsonResponse({
                'success': True,
                'added': result['added'],
                'duplicates': result['duplicates']
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to save hostnames'
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

def get_clustername_prefix_from_name(clustername):
    """Extract the prefix part of a clustername (everything before the last digits)"""
    # Find the last sequence of digits at the end of the string
    match = re.search(r'(.*?)(\d+)$', clustername)
    if match:
        return match.group(1)  # Return everything before the digits
    return clustername  # Return the original if no digits found

def find_next_available_clustername_sequence(clustername_prefix):
    """
    Find the next available sequence number for a clustername prefix
    More flexible to handle inconsistent naming conventions
    """
    # Get all existing clusternames
    existing_clusternames = get_existing_clusternames()
    
    # Get all existing hostnames (to avoid conflicts)
    existing_hostnames = get_existing_hostnames()
    
    # Combine all names
    all_existing_names = existing_clusternames + existing_hostnames
    
    # Filter names by matching prefix part (not using regex escape for more flexibility)
    matching_sequences = []
    
    for name in all_existing_names:
        # Get the prefix of the current name
        current_prefix = get_clustername_prefix_from_name(name)
        
        # If this prefix matches our target prefix, extract the sequence number
        if current_prefix.lower() == clustername_prefix.lower():
            # Extract the sequence number
            match = re.search(r'(\d+)$', name)
            if match:
                seq_num = int(match.group(1))
                matching_sequences.append(seq_num)
    
    debug_log(f"Found {len(matching_sequences)} matching sequences for prefix {clustername_prefix}")
    
    # If no matching sequences found, start from 1
    if not matching_sequences:
        return 1
    
    # Sort sequence numbers
    matching_sequences.sort()
    
    # Find the first gap in the sequence
    for i in range(len(matching_sequences)):
        if i == 0 and matching_sequences[0] > 1:
            return 1
        
        if i < len(matching_sequences) - 1:
            curr = matching_sequences[i]
            next_val = matching_sequences[i + 1]
            
            if next_val > curr + 1:
                return curr + 1
    
    # No gaps found, use next available number
    return matching_sequences[-1] + 1


def generate_clustername(datacenter, architecture, zone):
    """
    Generate a clustername with the format: datacenter + "-APAC-" + architecture + '-' + zone + "-" + sequence_number
    Now handles inconsistent naming patterns
    """
    # Create the base clustername without the sequence number
    base_clustername = f"{datacenter}-APAC-{architecture}-{zone}-"
    
    # Find the next available sequence number
    next_seq = find_next_available_clustername_sequence(base_clustername)
    
    # Create the full clustername with sequence number
    full_clustername = f"{base_clustername}{next_seq}"
    
    return full_clustername


def validate_clustername_exists(clustername):
    """
    Check if a clustername already exists, using the more flexible prefix matching
    """
    # Get the prefix of the clustername we're checking
    prefix_to_check = get_clustername_prefix_from_name(clustername)
    
    # Get sequence number of the clustername we're checking
    seq_match = re.search(r'(\d+)$', clustername)
    seq_to_check = int(seq_match.group(1)) if seq_match else None
    
    # Get all existing clusternames
    existing_clusternames = get_existing_clusternames()
    
    # Loop through existing clusternames
    for existing in existing_clusternames:
        existing_prefix = get_clustername_prefix_from_name(existing)
        
        # If prefixes match (case-insensitive)
        if existing_prefix.lower() == prefix_to_check.lower():
            # If we don't care about the sequence number, it's a match
            if seq_to_check is None:
                return True
                
            # If we have a sequence number, check that too
            existing_seq_match = re.search(r'(\d+)$', existing)
            if existing_seq_match:
                existing_seq = int(existing_seq_match.group(1))
                if existing_seq == seq_to_check:
                    return True
    
    return False


def find_next_available_hostname_sequence(hostname_prefix, is_dmz=False):
    """
    Find the next available sequence number for a hostname prefix
    Modified to use the more flexible prefix extraction
    """
    # Get all existing hostnames
    existing_hostnames = get_existing_hostnames()
    
    # Get all existing clusternames (to avoid conflicts)
    existing_clusternames = get_existing_clusternames()
    
    # Combine all names
    all_existing_names = existing_hostnames + existing_clusternames
    
    # Filter names by matching prefix part
    matching_sequences = []
    
    for name in all_existing_names:
        # Get the prefix of the current name
        current_prefix = get_clustername_prefix_from_name(name)
        
        # If this prefix matches our target prefix, extract the sequence number
        if current_prefix.lower() == hostname_prefix.lower():
            # Extract the sequence number
            match = re.search(r'(\d+)$', name)
            if match:
                seq_num = int(match.group(1))
                matching_sequences.append(seq_num)
    
    debug_log(f"Found {len(matching_sequences)} matching sequences for hostname prefix {hostname_prefix}")
    
    # If no matching sequences found, start from 1
    if not matching_sequences:
        return 1
    
    # Sort sequence numbers
    matching_sequences.sort()
    
    # Find the first gap in the sequence
    for i in range(len(matching_sequences)):
        if i == 0 and matching_sequences[0] > 1:
            # First number is greater than 1, so use 1
            return 1
        
        if i < len(matching_sequences) - 1:
            curr = matching_sequences[i]
            next_val = matching_sequences[i + 1]
            
            if next_val > curr + 1:
                # Found a gap, return the next number in sequence
                return curr + 1
    
    # No gaps found, use next available number
    return matching_sequences[-1] + 1

def check_clustername_view(request):
    """View to check if a clustername already exists"""
    if request.method == 'POST':
        clustername = request.POST.get('clustername')
        
        # Run the test function if a special flag is set
        if request.POST.get('test_mode') == 'true':
            test_clustername_matching()
            return JsonResponse({'success': True, 'message': 'Test completed, check server logs'})
        
        # Extract the prefix
        prefix = get_clustername_prefix_from_name(clustername)
        
        # Find the next available sequence
        next_seq = find_next_available_clustername_sequence(prefix)
        
        return JsonResponse({
            'success': True,
            'exists': validate_clustername_exists(clustername),
            'prefix': prefix,
            'next_available_sequence': next_seq,
            'suggested_name': f"{prefix}{next_seq}"
        })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})