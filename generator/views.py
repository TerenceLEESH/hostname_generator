from django.shortcuts import render, redirect
from django.http import JsonResponse
import csv
import os
from .forms import HostnameQuestionnaireForm
from .models import Hostname

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

def generate_hostnames(data, datacenters):
    """Generate hostnames based on form data"""
    hostnames = []
    
    # Get the count of hostnames to generate
    count = int(data.get('hostname_count', 1))
    
    # Get the datacenter code
    datacenter_name = data.get('datacenter', '')
    datacenter_code = next((dc['sitecode'] for dc in datacenters if dc['datacenter'] == datacenter_name), 'DC')
    
    # Determine components based on form answers
    prefix = 'ESXI'
    
    # DMZ or hardware type
    if data.get('is_dmz') == 'True':
        component2 = 'DMZ'
    else:
        component2 = data.get('hardware_type', '')
    
    # Cloud code
    component3 = data.get('cloud_code', '')
    
    # Zone type
    component4 = data.get('zone_type', '')
    
    # If not existing cluster, add architecture and zone
    if data.get('existing_cluster') == 'False':
        architecture = data.get('service_architecture', '')
        zone = data.get('zone', '')
        
        # Generate hostnames
        for i in range(1, count + 1):
            hostname = f"{prefix}-{component2}-{component3}-{component4}-{architecture}-{zone}-{datacenter_code}-{i:02d}"
            hostnames.append(hostname)
    else:
        # Generate hostnames without architecture and zone
        for i in range(1, count + 1):
            hostname = f"{prefix}-{component2}-{component3}-{component4}-{datacenter_code}-{i:02d}"
            hostnames.append(hostname)
    
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

    # Initialize form and step data
    # form = HostnameQuestionnaireForm(request.POST or None)
    
    # Get current step from session or default to 1
    current_step = request.session.get('current_step', 1)
    total_steps = 9  # Total number of questions
    
    # Load datacenters for Q5
    # datacenters = load_datacenters_from_csv()
    
    # Handle step navigation
    if request.method == 'POST':
        if 'next_step' in request.POST and current_step < total_steps:
            # Save current step data to session
            request.session[f'step_{current_step}_data'] = request.POST.dict()
            
            # Special case: If on step 1 and existing_cluster is True, skip to step 4
            if current_step == 1 and request.POST.get('existing_cluster') == 'True':
                current_step = 4  # Skip questions 2 and 3
            # Standard next step
            else:
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
            
            # Remove navigation keys
            for key in ['next_step', 'prev_step', 'submit', 'csrfmiddlewaretoken']:
                if key in all_data:
                    del all_data[key]
            
            # Generate hostnames based on collected data
            hostnames = generate_hostnames(all_data, datacenters)
            
            # Generate cluster name if needed
            clustername = None
            if all_data.get('existing_cluster') == 'False':
                clustername = generate_clustername(all_data, datacenters)
                
                # Check if cluster name already exists
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
            
            # Check if hostnames already exist
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
            
            # Save the hostnames and cluster name
            saved_hostnames = []
            for hostname in hostnames:
                # Save to DataFrame
                Hostname.add_hostname_to_df(hostname)
                saved_hostnames.append(hostname)
            
            # Save cluster name if generated
            if clustername:
                Hostname.add_clustername_to_df(clustername)
            
            # Clear session data
            for step in range(1, total_steps + 1):
                if f'step_{step}_data' in request.session:
                    del request.session[f'step_{step}_data']
            if 'current_step' in request.session:
                del request.session['current_step']
            
            return render(request, 'generator/result.html', {
                'hostnames': saved_hostnames,
                'hostname_count': len(saved_hostnames),
                'clustername': clustername
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

def index(request):
    """Alias for the esxi_hostname_generator view"""
    return esxi_hostname_generator(request)