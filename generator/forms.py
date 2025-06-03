from django import forms

class HostnameQuestionnaireForm(forms.Form):
    # Question 1: Is it under an existing cluster?
    existing_cluster = forms.BooleanField(
        label="Is it under an existing cluster?",
        required=False,
        widget=forms.RadioSelect(choices=[(True, 'Yes'), (False, 'No')])
    )
    
    # Question 2: OSA or ESA? (Only if Q1 was No)
    service_architecture = forms.ChoiceField(
        label="OSA or ESA?",
        choices=[('OSA', 'OSA'), ('ESA', 'ESA')],
        required=False
    )
    
    # Question 3: Which zone? (Only if Q1 was No)
    zone = forms.ChoiceField(
        label="Which zone it belongs to?",
        choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D'), ('E', 'E')],
        required=False
    )
    
    # Question 4: How many ESXi hostnames?
    hostname_count = forms.IntegerField(
        label="How many ESXi hostnames do you need?",
        min_value=1,
        max_value=100,
        initial=1
    )
    
    # Question 5: Select the datacenter
    datacenter = forms.ChoiceField(
        label="Select the datacenter",
        choices=[]  # Will be populated dynamically
    )
    
    # Question 6: Is this host in DMZ?
    is_dmz = forms.BooleanField(
        label="Is this host in DMZ?",
        required=False,
        widget=forms.RadioSelect(choices=[(True, 'Yes'), (False, 'No')])
    )
    
    # Question 7: Hardware type (Only if Q6 was No)
    hardware_type = forms.ChoiceField(
        label="Hardware type",
        choices=[('Dell', 'Dell'), ('HP', 'HP')],
        required=False
    )
    
    # Question 8: Select the cloud code
    cloud_code = forms.ChoiceField(
        label="Select the cloud code",
        choices=[('QQA', 'QQA'), ('QQB', 'QQB'), ('QQC', 'QQC'), ('custom', 'Custom (specify)')]
    )
    
    # Custom cloud code field for when "Custom" is selected in Question 8
    custom_cloud_code = forms.CharField(
        label="Enter custom cloud code",
        max_length=10,
        required=False,
        help_text="Please enter a custom cloud code (max 10 characters)"
    )
    
    # Question 9: Select the zone type
    zone_type = forms.ChoiceField(
        label="Select the zone type",
        choices=[('AAA', 'AAA'), ('BBB', 'BBB'), ('CCC', 'CCC')]
    )
    
    def __init__(self, *args, **kwargs):
        # Get datacenters from kwargs if provided
        datacenters = kwargs.pop('datacenters', None)
        super().__init__(*args, **kwargs)
        
        # Populate datacenter choices if provided
        if datacenters:
            self.fields['datacenter'].choices = [(dc['datacenter'], f"{dc['datacenter']} ({dc['sitecode']})") for dc in datacenters]
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Validate existing_cluster dependencies
        existing_cluster = cleaned_data.get('existing_cluster')
        
        if existing_cluster is None:
            self.add_error('existing_cluster', 'Please select whether this is under an existing cluster.')
        
        # If not existing cluster, require architecture and zone
        if existing_cluster is False:
            if not cleaned_data.get('service_architecture'):
                self.add_error('service_architecture', 'This field is required when creating a new cluster.')
            
            if not cleaned_data.get('zone'):
                self.add_error('zone', 'This field is required when creating a new cluster.')
        
        # Validate is_dmz
        is_dmz = cleaned_data.get('is_dmz')
        
        if is_dmz is None:
            self.add_error('is_dmz', 'Please select whether this host is in DMZ.')
        
        # If not DMZ, require hardware_type
        if is_dmz is False and not cleaned_data.get('hardware_type'):
            self.add_error('hardware_type', 'Hardware type is required for non-DMZ hosts.')
        
        # Validate custom cloud code if custom option is selected
        cloud_code = cleaned_data.get('cloud_code')
        custom_cloud_code = cleaned_data.get('custom_cloud_code')
        
        if cloud_code == 'custom':
            if not custom_cloud_code:
                self.add_error('custom_cloud_code', 'Please enter a custom cloud code.')
            else:
                # Store the custom value in cloud_code for easier processing later
                cleaned_data['cloud_code'] = custom_cloud_code
        
        return cleaned_data