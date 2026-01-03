import boto3
import time
import os
import sys
import json
import threading
import requests
from botocore.exceptions import ClientError, BotoCoreError
from datetime import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import configparser
import uuid
import hashlib
from pathlib import Path

class OnlineKeyValidator:
    """Validates license keys against an online API"""
    
    def __init__(self, api_url="https://api.example.com/validate"):
        self.api_url = api_url
        self.machine_id = self._get_machine_id()
        
    def _get_machine_id(self):
        """Generate a unique machine identifier"""
        if sys.platform == 'win32':
            import subprocess
            try:
                output = subprocess.check_output('wmic csproduct get uuid', shell=True)
                machine_id = output.decode().split('\n')[1].strip()
            except:
                machine_id = str(uuid.getnode())
        else:
            machine_id = str(uuid.getnode())
        
        return hashlib.sha256(machine_id.encode()).hexdigest()
    
    def validate_key(self, license_key):
        """
        Validate license key against online API
        Returns: (is_valid, message, user_info)
        """
        try:
            payload = {
                'license_key': license_key,
                'machine_id': self.machine_id,
                'product': 'AWS_Proxy_Generator',
                'version': '4.0'
            }
            
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('valid'):
                    return True, "License activated successfully", data.get('user_info', {})
                else:
                    return False, data.get('message', 'Invalid license key'), None
            else:
                return False, f"Server error: {response.status_code}", None
                
        except requests.RequestException as e:
            return False, f"Connection error: {str(e)}", None
        except Exception as e:
            return False, f"Validation error: {str(e)}", None

class UsageCounter:
    """Tracks usage statistics"""
    
    def __init__(self, stats_file="usage_stats.json"):
        self.stats_file = stats_file
        self.stats = self._load_stats()
        
    def _load_stats(self):
        """Load statistics from file"""
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        
        return {
            'total_instances_created': 0,
            'total_ips_renewed': 0,
            'total_sessions': 0,
            'last_used': None,
            'first_used': None
        }
    
    def _save_stats(self):
        """Save statistics to file"""
        try:
            with open(self.stats_file, 'w') as f:
                json.dump(self.stats, f, indent=2)
        except:
            pass
    
    def increment_instances(self, count=1):
        """Increment instance creation counter"""
        self.stats['total_instances_created'] += count
        self._save_stats()
    
    def increment_renewals(self, count=1):
        """Increment IP renewal counter"""
        self.stats['total_ips_renewed'] += count
        self._save_stats()
    
    def increment_sessions(self):
        """Increment session counter"""
        self.stats['total_sessions'] += 1
        self.stats['last_used'] = datetime.now().isoformat()
        if not self.stats['first_used']:
            self.stats['first_used'] = self.stats['last_used']
        self._save_stats()
    
    def get_stats(self):
        """Get current statistics"""
        return self.stats.copy()

class UsageReporter:
    """Reports usage to online server"""
    
    def __init__(self, api_url="https://api.example.com/usage"):
        self.api_url = api_url
        self.machine_id = self._get_machine_id()
        
    def _get_machine_id(self):
        """Generate a unique machine identifier"""
        if sys.platform == 'win32':
            import subprocess
            try:
                output = subprocess.check_output('wmic csproduct get uuid', shell=True)
                machine_id = output.decode().split('\n')[1].strip()
            except:
                machine_id = str(uuid.getnode())
        else:
            machine_id = str(uuid.getnode())
        
        return hashlib.sha256(machine_id.encode()).hexdigest()
    
    def report_usage(self, license_key, action, details=None):
        """
        Report usage to server
        action: 'create_instance', 'renew_ip', 'start_session', etc.
        """
        try:
            payload = {
                'license_key': license_key,
                'machine_id': self.machine_id,
                'action': action,
                'details': details or {},
                'timestamp': datetime.now().isoformat(),
                'product': 'AWS_Proxy_Generator',
                'version': '4.0'
            }
            
            # Send in background thread to not block UI
            thread = threading.Thread(
                target=self._send_report,
                args=(payload,),
                daemon=True
            )
            thread.start()
            
        except Exception as e:
            # Silently fail - don't interrupt user experience
            pass
    
    def _send_report(self, payload):
        """Send report to server (run in background thread)"""
        try:
            requests.post(
                self.api_url,
                json=payload,
                timeout=5
            )
        except:
            pass

class LoadingDialog:
    """Loading dialog with progress indication"""
    
    def __init__(self, parent, title="Loading", message="Please wait..."):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.geometry("400x150")
        self.dialog.resizable(False, False)
        
        # Center on parent
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 400) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 150) // 2
        self.dialog.geometry(f"+{x}+{y}")
        
        # Message label
        self.label = tk.Label(
            self.dialog,
            text=message,
            font=("Arial", 10),
            wraplength=350
        )
        self.label.pack(pady=20)
        
        # Progress bar
        self.progress = ttk.Progressbar(
            self.dialog,
            mode='indeterminate',
            length=350
        )
        self.progress.pack(pady=10)
        self.progress.start(10)
        
        # Status label
        self.status_label = tk.Label(
            self.dialog,
            text="",
            font=("Arial", 8),
            fg="gray"
        )
        self.status_label.pack(pady=5)
        
    def update_message(self, message):
        """Update the main message"""
        self.label.config(text=message)
        self.dialog.update()
        
    def update_status(self, status):
        """Update the status label"""
        self.status_label.config(text=status)
        self.dialog.update()
        
    def close(self):
        """Close the dialog"""
        self.progress.stop()
        self.dialog.grab_release()
        self.dialog.destroy()

class AWSProxyGenerator:
    def __init__(self, master):
        self.master = master
        self.master.title("AWS Proxy Generator v4.0")
        self.master.geometry("1000x700")
        
        # Initialize components
        self.key_validator = OnlineKeyValidator()
        self.usage_counter = UsageCounter()
        self.usage_reporter = UsageReporter()
        
        # License state
        self.is_licensed = False
        self.license_key = ""
        self.user_info = {}
        
        # AWS credentials
        self.aws_access_key = ""
        self.aws_secret_key = ""
        self.region = "us-east-1"
        
        # Instance tracking
        self.instances = []
        self.ec2_client = None
        
        # Configuration file
        self.config_file = "aws_proxy_config.ini"
        
        # Load saved configuration
        self.load_config()
        
        # Create GUI
        self.create_widgets()
        
        # Check license on startup
        if self.license_key:
            self.verify_license_silent()
    
    def create_widgets(self):
        """Create all GUI widgets"""
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.master)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # License Tab
        self.license_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.license_frame, text="License")
        self.create_license_tab()
        
        # Configuration Tab
        self.config_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.config_frame, text="Configuration")
        self.create_config_tab()
        
        # Instances Tab
        self.instances_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.instances_frame, text="Instances")
        self.create_instances_tab()
        
        # Logs Tab
        self.logs_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.logs_frame, text="Logs")
        self.create_logs_tab()
        
        # Statistics Tab
        self.stats_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.stats_frame, text="Statistics")
        self.create_stats_tab()
        
        # Status bar
        self.status_bar = tk.Label(
            self.master,
            text="Ready",
            bd=1,
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def create_license_tab(self):
        """Create license activation tab"""
        
        # Title
        title = tk.Label(
            self.license_frame,
            text="License Activation",
            font=("Arial", 16, "bold")
        )
        title.pack(pady=20)
        
        # License status frame
        status_frame = tk.LabelFrame(
            self.license_frame,
            text="License Status",
            font=("Arial", 10, "bold")
        )
        status_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.license_status_label = tk.Label(
            status_frame,
            text="Not Activated",
            font=("Arial", 12),
            fg="red"
        )
        self.license_status_label.pack(pady=10)
        
        self.license_info_label = tk.Label(
            status_frame,
            text="",
            font=("Arial", 9),
            fg="gray"
        )
        self.license_info_label.pack(pady=5)
        
        # License key entry frame
        entry_frame = tk.LabelFrame(
            self.license_frame,
            text="Enter License Key",
            font=("Arial", 10, "bold")
        )
        entry_frame.pack(fill=tk.X, padx=20, pady=10)
        
        key_frame = tk.Frame(entry_frame)
        key_frame.pack(pady=10)
        
        tk.Label(key_frame, text="License Key:", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        
        self.license_key_entry = tk.Entry(key_frame, width=40, font=("Arial", 10))
        self.license_key_entry.pack(side=tk.LEFT, padx=5)
        
        if self.license_key:
            self.license_key_entry.insert(0, self.license_key)
        
        activate_btn = tk.Button(
            key_frame,
            text="Activate",
            command=self.activate_license,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=20
        )
        activate_btn.pack(side=tk.LEFT, padx=5)
        
        # Machine ID info
        machine_frame = tk.LabelFrame(
            self.license_frame,
            text="Machine Information",
            font=("Arial", 10, "bold")
        )
        machine_frame.pack(fill=tk.X, padx=20, pady=10)
        
        machine_id = self.key_validator.machine_id
        machine_text = f"Machine ID: {machine_id[:32]}..."
        
        tk.Label(
            machine_frame,
            text=machine_text,
            font=("Arial", 9),
            fg="gray"
        ).pack(pady=10)
        
        tk.Label(
            machine_frame,
            text="(This ID is used to bind your license to this machine)",
            font=("Arial", 8),
            fg="gray"
        ).pack(pady=5)
    
    def create_config_tab(self):
        """Create AWS configuration tab"""
        
        # Title
        title = tk.Label(
            self.config_frame,
            text="AWS Configuration",
            font=("Arial", 16, "bold")
        )
        title.pack(pady=20)
        
        # AWS Credentials frame
        creds_frame = tk.LabelFrame(
            self.config_frame,
            text="AWS Credentials",
            font=("Arial", 10, "bold")
        )
        creds_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Access Key
        ak_frame = tk.Frame(creds_frame)
        ak_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(ak_frame, text="Access Key ID:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=5)
        self.access_key_entry = tk.Entry(ak_frame, width=50, show="*")
        self.access_key_entry.pack(side=tk.LEFT, padx=5)
        self.access_key_entry.insert(0, self.aws_access_key)
        
        # Secret Key
        sk_frame = tk.Frame(creds_frame)
        sk_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(sk_frame, text="Secret Access Key:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=5)
        self.secret_key_entry = tk.Entry(sk_frame, width=50, show="*")
        self.secret_key_entry.pack(side=tk.LEFT, padx=5)
        self.secret_key_entry.insert(0, self.aws_secret_key)
        
        # Region
        region_frame = tk.Frame(creds_frame)
        region_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(region_frame, text="Region:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=5)
        self.region_var = tk.StringVar(value=self.region)
        regions = [
            "us-east-1", "us-east-2", "us-west-1", "us-west-2",
            "eu-west-1", "eu-west-2", "eu-central-1",
            "ap-southeast-1", "ap-southeast-2", "ap-northeast-1"
        ]
        region_combo = ttk.Combobox(
            region_frame,
            textvariable=self.region_var,
            values=regions,
            width=47,
            state="readonly"
        )
        region_combo.pack(side=tk.LEFT, padx=5)
        
        # Buttons
        btn_frame = tk.Frame(creds_frame)
        btn_frame.pack(pady=10)
        
        save_btn = tk.Button(
            btn_frame,
            text="Save Configuration",
            command=self.save_aws_config,
            bg="#2196F3",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=20
        )
        save_btn.pack(side=tk.LEFT, padx=5)
        
        test_btn = tk.Button(
            btn_frame,
            text="Test Connection",
            command=self.test_aws_connection,
            bg="#FF9800",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=20
        )
        test_btn.pack(side=tk.LEFT, padx=5)
        
        # Instance Settings frame
        settings_frame = tk.LabelFrame(
            self.config_frame,
            text="Instance Settings",
            font=("Arial", 10, "bold")
        )
        settings_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Instance Count
        count_frame = tk.Frame(settings_frame)
        count_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(count_frame, text="Number of Instances:", width=20, anchor=tk.W).pack(side=tk.LEFT, padx=5)
        self.instance_count_var = tk.IntVar(value=1)
        instance_count_spin = tk.Spinbox(
            count_frame,
            from_=1,
            to=10,
            textvariable=self.instance_count_var,
            width=10
        )
        instance_count_spin.pack(side=tk.LEFT, padx=5)
        
        # Instance Type
        type_frame = tk.Frame(settings_frame)
        type_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(type_frame, text="Instance Type:", width=20, anchor=tk.W).pack(side=tk.LEFT, padx=5)
        self.instance_type_var = tk.StringVar(value="t2.micro")
        instance_types = ["t2.micro", "t2.small", "t2.medium", "t3.micro", "t3.small"]
        type_combo = ttk.Combobox(
            type_frame,
            textvariable=self.instance_type_var,
            values=instance_types,
            width=15,
            state="readonly"
        )
        type_combo.pack(side=tk.LEFT, padx=5)
    
    def create_instances_tab(self):
        """Create instances management tab"""
        
        # Title
        title = tk.Label(
            self.instances_frame,
            text="Instance Management",
            font=("Arial", 16, "bold")
        )
        title.pack(pady=20)
        
        # Control buttons frame
        control_frame = tk.Frame(self.instances_frame)
        control_frame.pack(fill=tk.X, padx=20, pady=10)
        
        create_btn = tk.Button(
            control_frame,
            text="Create Instances",
            command=self.create_instances,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=20
        )
        create_btn.pack(side=tk.LEFT, padx=5)
        
        refresh_btn = tk.Button(
            control_frame,
            text="Refresh List",
            command=self.refresh_instances,
            bg="#2196F3",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=20
        )
        refresh_btn.pack(side=tk.LEFT, padx=5)
        
        renew_btn = tk.Button(
            control_frame,
            text="Renew All IPs",
            command=self.renew_all_ips,
            bg="#FF9800",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=20
        )
        renew_btn.pack(side=tk.LEFT, padx=5)
        
        terminate_btn = tk.Button(
            control_frame,
            text="Terminate All",
            command=self.terminate_all_instances,
            bg="#f44336",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=20
        )
        terminate_btn.pack(side=tk.LEFT, padx=5)
        
        export_btn = tk.Button(
            control_frame,
            text="Export Proxies",
            command=self.export_proxies,
            bg="#9C27B0",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=20
        )
        export_btn.pack(side=tk.LEFT, padx=5)
        
        # Instances list frame
        list_frame = tk.LabelFrame(
            self.instances_frame,
            text="Active Instances",
            font=("Arial", 10, "bold")
        )
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Create treeview for instances
        columns = ("Instance ID", "Public IP", "Status", "Type", "Region")
        self.instances_tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="tree headings",
            height=15
        )
        
        # Configure columns
        self.instances_tree.column("#0", width=0, stretch=tk.NO)
        for col in columns:
            self.instances_tree.heading(col, text=col)
            self.instances_tree.column(col, width=150)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(
            list_frame,
            orient=tk.VERTICAL,
            command=self.instances_tree.yview
        )
        self.instances_tree.configure(yscrollcommand=scrollbar.set)
        
        self.instances_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Context menu for instances
        self.instances_menu = tk.Menu(self.instances_tree, tearoff=0)
        self.instances_menu.add_command(label="Renew IP", command=self.renew_selected_ip)
        self.instances_menu.add_command(label="Terminate", command=self.terminate_selected_instance)
        self.instances_menu.add_separator()
        self.instances_menu.add_command(label="Copy IP", command=self.copy_selected_ip)
        
        self.instances_tree.bind("<Button-3>", self.show_instance_menu)
    
    def create_logs_tab(self):
        """Create logs display tab"""
        
        # Title
        title = tk.Label(
            self.logs_frame,
            text="Activity Logs",
            font=("Arial", 16, "bold")
        )
        title.pack(pady=20)
        
        # Control buttons
        control_frame = tk.Frame(self.logs_frame)
        control_frame.pack(fill=tk.X, padx=20, pady=5)
        
        clear_btn = tk.Button(
            control_frame,
            text="Clear Logs",
            command=self.clear_logs,
            bg="#f44336",
            fg="white",
            font=("Arial", 9, "bold")
        )
        clear_btn.pack(side=tk.LEFT, padx=5)
        
        save_btn = tk.Button(
            control_frame,
            text="Save Logs",
            command=self.save_logs,
            bg="#2196F3",
            fg="white",
            font=("Arial", 9, "bold")
        )
        save_btn.pack(side=tk.LEFT, padx=5)
        
        # Log display
        log_frame = tk.Frame(self.logs_frame)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            width=100,
            height=30,
            font=("Courier", 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Configure tags for colored logs
        self.log_text.tag_config("INFO", foreground="black")
        self.log_text.tag_config("SUCCESS", foreground="green")
        self.log_text.tag_config("WARNING", foreground="orange")
        self.log_text.tag_config("ERROR", foreground="red")
    
    def create_stats_tab(self):
        """Create statistics display tab"""
        
        # Title
        title = tk.Label(
            self.stats_frame,
            text="Usage Statistics",
            font=("Arial", 16, "bold")
        )
        title.pack(pady=20)
        
        # Statistics display
        stats_display_frame = tk.LabelFrame(
            self.stats_frame,
            text="Lifetime Statistics",
            font=("Arial", 10, "bold")
        )
        stats_display_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.stats_labels = {}
        
        stats_keys = [
            ("Total Instances Created", "total_instances_created"),
            ("Total IPs Renewed", "total_ips_renewed"),
            ("Total Sessions", "total_sessions"),
            ("First Used", "first_used"),
            ("Last Used", "last_used")
        ]
        
        for i, (label_text, key) in enumerate(stats_keys):
            frame = tk.Frame(stats_display_frame)
            frame.pack(fill=tk.X, padx=20, pady=5)
            
            tk.Label(
                frame,
                text=f"{label_text}:",
                font=("Arial", 10, "bold"),
                width=25,
                anchor=tk.W
            ).pack(side=tk.LEFT, padx=5)
            
            value_label = tk.Label(
                frame,
                text="0",
                font=("Arial", 10),
                anchor=tk.W
            )
            value_label.pack(side=tk.LEFT, padx=5)
            
            self.stats_labels[key] = value_label
        
        # Refresh button
        refresh_btn = tk.Button(
            self.stats_frame,
            text="Refresh Statistics",
            command=self.refresh_statistics,
            bg="#2196F3",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=20
        )
        refresh_btn.pack(pady=10)
        
        # Load initial stats
        self.refresh_statistics()
    
    # License Management Methods
    
    def activate_license(self):
        """Activate license key"""
        license_key = self.license_key_entry.get().strip()
        
        if not license_key:
            messagebox.showerror("Error", "Please enter a license key")
            return
        
        # Show loading dialog
        loading = LoadingDialog(self.master, "Activating License", "Validating license key...")
        
        # Validate in background thread
        def validate():
            is_valid, message, user_info = self.key_validator.validate_key(license_key)
            
            # Update UI in main thread
            self.master.after(0, lambda: self.handle_license_result(
                is_valid, message, user_info, license_key, loading
            ))
        
        thread = threading.Thread(target=validate, daemon=True)
        thread.start()
    
    def handle_license_result(self, is_valid, message, user_info, license_key, loading):
        """Handle license validation result"""
        loading.close()
        
        if is_valid:
            self.is_licensed = True
            self.license_key = license_key
            self.user_info = user_info or {}
            
            # Update UI
            self.license_status_label.config(text="✓ Activated", fg="green")
            
            info_text = f"Licensed to: {self.user_info.get('name', 'N/A')}\n"
            info_text += f"Email: {self.user_info.get('email', 'N/A')}\n"
            info_text += f"Expires: {self.user_info.get('expires', 'Never')}"
            self.license_info_label.config(text=info_text)
            
            # Save to config
            self.save_config()
            
            # Report usage
            self.usage_reporter.report_usage(license_key, 'activate_license')
            self.usage_counter.increment_sessions()
            
            messagebox.showinfo("Success", "License activated successfully!")
            
            # Switch to config tab
            self.notebook.select(self.config_frame)
        else:
            self.is_licensed = False
            self.license_status_label.config(text="✗ Not Activated", fg="red")
            self.license_info_label.config(text="")
            messagebox.showerror("License Error", message)
    
    def verify_license_silent(self):
        """Verify license silently on startup"""
        if not self.license_key:
            return
        
        def validate():
            is_valid, message, user_info = self.key_validator.validate_key(self.license_key)
            
            self.master.after(0, lambda: self.update_license_status(is_valid, user_info))
        
        thread = threading.Thread(target=validate, daemon=True)
        thread.start()
    
    def update_license_status(self, is_valid, user_info):
        """Update license status after silent verification"""
        if is_valid:
            self.is_licensed = True
            self.user_info = user_info or {}
            self.license_status_label.config(text="✓ Activated", fg="green")
            
            info_text = f"Licensed to: {self.user_info.get('name', 'N/A')}\n"
            info_text += f"Email: {self.user_info.get('email', 'N/A')}\n"
            info_text += f"Expires: {self.user_info.get('expires', 'Never')}"
            self.license_info_label.config(text=info_text)
            
            self.usage_counter.increment_sessions()
        else:
            self.is_licensed = False
            self.license_status_label.config(text="✗ Not Activated", fg="red")
            self.license_info_label.config(text="")
    
    # AWS Configuration Methods
    
    def save_aws_config(self):
        """Save AWS configuration"""
        self.aws_access_key = self.access_key_entry.get().strip()
        self.aws_secret_key = self.secret_key_entry.get().strip()
        self.region = self.region_var.get()
        
        if not self.aws_access_key or not self.aws_secret_key:
            messagebox.showerror("Error", "Please enter AWS credentials")
            return
        
        self.save_config()
        self.log("INFO", "AWS configuration saved")
        messagebox.showinfo("Success", "AWS configuration saved successfully!")
    
    def test_aws_connection(self):
        """Test AWS connection"""
        if not self.is_licensed:
            messagebox.showerror("Error", "Please activate your license first")
            return
        
        if not self.aws_access_key or not self.aws_secret_key:
            messagebox.showerror("Error", "Please enter AWS credentials first")
            return
        
        loading = LoadingDialog(self.master, "Testing Connection", "Connecting to AWS...")
        
        def test():
            try:
                ec2 = boto3.client(
                    'ec2',
                    aws_access_key_id=self.aws_access_key,
                    aws_secret_access_key=self.aws_secret_key,
                    region_name=self.region
                )
                
                # Try to describe instances
                ec2.describe_instances()
                
                self.master.after(0, lambda: self.handle_connection_result(True, None, loading))
            except Exception as e:
                self.master.after(0, lambda: self.handle_connection_result(False, str(e), loading))
        
        thread = threading.Thread(target=test, daemon=True)
        thread.start()
    
    def handle_connection_result(self, success, error, loading):
        """Handle connection test result"""
        loading.close()
        
        if success:
            self.log("SUCCESS", "AWS connection successful")
            messagebox.showinfo("Success", "Successfully connected to AWS!")
        else:
            self.log("ERROR", f"AWS connection failed: {error}")
            messagebox.showerror("Connection Error", f"Failed to connect to AWS:\n{error}")
    
    # Instance Management Methods
    
    def create_instances(self):
        """Create EC2 instances"""
        if not self.is_licensed:
            messagebox.showerror("Error", "Please activate your license first")
            return
        
        if not self.aws_access_key or not self.aws_secret_key:
            messagebox.showerror("Error", "Please configure AWS credentials first")
            return
        
        count = self.instance_count_var.get()
        instance_type = self.instance_type_var.get()
        
        loading = LoadingDialog(
            self.master,
            "Creating Instances",
            f"Creating {count} EC2 instance(s)..."
        )
        
        def create():
            try:
                ec2 = boto3.client(
                    'ec2',
                    aws_access_key_id=self.aws_access_key,
                    aws_secret_access_key=self.aws_secret_key,
                    region_name=self.region
                )
                
                self.master.after(0, lambda: loading.update_status("Launching instances..."))
                
                # Get latest Amazon Linux 2 AMI
                response = ec2.describe_images(
                    Owners=['amazon'],
                    Filters=[
                        {'Name': 'name', 'Values': ['amzn2-ami-hvm-*-x86_64-gp2']},
                        {'Name': 'state', 'Values': ['available']}
                    ]
                )
                
                if not response['Images']:
                    raise Exception("No suitable AMI found")
                
                # Sort by creation date and get the latest
                images = sorted(response['Images'], key=lambda x: x['CreationDate'], reverse=True)
                ami_id = images[0]['ImageId']
                
                # User data script to install and configure Squid proxy
                user_data_script = '''#!/bin/bash
yum update -y
yum install -y squid httpd-tools

# Configure Squid
cat > /etc/squid/squid.conf << 'EOF'
http_port 3128

acl localnet src 0.0.0.0/0
acl SSL_ports port 443
acl Safe_ports port 80
acl Safe_ports port 443
acl CONNECT method CONNECT

http_access deny !Safe_ports
http_access deny CONNECT !SSL_ports
http_access allow localnet
http_access allow localhost
http_access deny all

forwarded_for delete
via off
request_header_access X-Forwarded-For deny all
request_header_access Via deny all
request_header_access Cache-Control deny all

cache deny all
EOF

# Start Squid
systemctl start squid
systemctl enable squid

# Open port 3128
firewall-cmd --permanent --add-port=3128/tcp
firewall-cmd --reload
'''
                
                # Launch instances
                response = ec2.run_instances(
                    ImageId=ami_id,
                    InstanceType=instance_type,
                    MinCount=count,
                    MaxCount=count,
                    UserData=user_data_script,
                    SecurityGroups=['default'],
                    TagSpecifications=[
                        {
                            'ResourceType': 'instance',
                            'Tags': [
                                {'Key': 'Name', 'Value': 'ProxyServer'},
                                {'Key': 'ManagedBy', 'Value': 'AWSProxyGenerator'}
                            ]
                        }
                    ]
                )
                
                instance_ids = [inst['InstanceId'] for inst in response['Instances']]
                
                self.master.after(0, lambda: loading.update_status("Waiting for instances to start..."))
                
                # Wait for instances to be running
                waiter = ec2.get_waiter('instance_running')
                waiter.wait(InstanceIds=instance_ids)
                
                self.master.after(0, lambda: loading.update_status("Allocating Elastic IPs..."))
                
                # Allocate and associate Elastic IPs
                for instance_id in instance_ids:
                    eip = ec2.allocate_address(Domain='vpc')
                    ec2.associate_address(
                        InstanceId=instance_id,
                        AllocationId=eip['AllocationId']
                    )
                
                # Update usage
                self.usage_counter.increment_instances(count)
                self.usage_reporter.report_usage(
                    self.license_key,
                    'create_instances',
                    {'count': count, 'type': instance_type, 'region': self.region}
                )
                
                self.master.after(0, lambda: self.handle_create_result(True, None, loading, count))
            except Exception as e:
                self.master.after(0, lambda: self.handle_create_result(False, str(e), loading, 0))
        
        thread = threading.Thread(target=create, daemon=True)
        thread.start()
    
    def handle_create_result(self, success, error, loading, count):
        """Handle instance creation result"""
        loading.close()
        
        if success:
            self.log("SUCCESS", f"Successfully created {count} instance(s)")
            messagebox.showinfo("Success", f"Successfully created {count} instance(s)!")
            self.refresh_instances()
        else:
            self.log("ERROR", f"Failed to create instances: {error}")
            messagebox.showerror("Error", f"Failed to create instances:\n{error}")
    
    def refresh_instances(self):
        """Refresh instances list"""
        if not self.aws_access_key or not self.aws_secret_key:
            return
        
        try:
            ec2 = boto3.client(
                'ec2',
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
                region_name=self.region
            )
            
            # Get instances
            response = ec2.describe_instances(
                Filters=[
                    {'Name': 'tag:ManagedBy', 'Values': ['AWSProxyGenerator']},
                    {'Name': 'instance-state-name', 'Values': ['running', 'pending', 'stopping', 'stopped']}
                ]
            )
            
            # Clear tree
            for item in self.instances_tree.get_children():
                self.instances_tree.delete(item)
            
            # Populate tree
            self.instances = []
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    instance_id = instance['InstanceId']
                    public_ip = instance.get('PublicIpAddress', 'N/A')
                    state = instance['State']['Name']
                    instance_type = instance['InstanceType']
                    
                    self.instances.append({
                        'id': instance_id,
                        'ip': public_ip,
                        'state': state,
                        'type': instance_type
                    })
                    
                    self.instances_tree.insert(
                        '',
                        tk.END,
                        values=(instance_id, public_ip, state, instance_type, self.region)
                    )
            
            self.log("INFO", f"Refreshed instances list: {len(self.instances)} instance(s) found")
            self.status_bar.config(text=f"Found {len(self.instances)} instance(s)")
        
        except Exception as e:
            self.log("ERROR", f"Failed to refresh instances: {str(e)}")
    
    def renew_all_ips(self):
        """Renew IPs for all instances using STOP→START method"""
        if not self.is_licensed:
            messagebox.showerror("Error", "Please activate your license first")
            return
        
        if not self.instances:
            messagebox.showwarning("Warning", "No instances found")
            return
        
        if not messagebox.askyesno("Confirm", "Renew IPs for all instances?\nThis will STOP and START instances, changing their public IPs."):
            return
        
        loading = LoadingDialog(
            self.master,
            "Renewing IPs",
            "Renewing IPs for all instances using STOP→START method..."
        )
        
        def renew():
            try:
                ec2 = boto3.client(
                    'ec2',
                    aws_access_key_id=self.aws_access_key,
                    aws_secret_access_key=self.aws_secret_key,
                    region_name=self.region
                )
                
                instance_ids = [inst['id'] for inst in self.instances if inst['state'] == 'running']
                
                if not instance_ids:
                    raise Exception("No running instances to renew")
                
                # Stop instances
                self.master.after(0, lambda: loading.update_status("Stopping instances..."))
                ec2.stop_instances(InstanceIds=instance_ids)
                
                # Wait for instances to stop
                waiter = ec2.get_waiter('instance_stopped')
                waiter.wait(InstanceIds=instance_ids)
                
                # Start instances
                self.master.after(0, lambda: loading.update_status("Starting instances..."))
                ec2.start_instances(InstanceIds=instance_ids)
                
                # Wait for instances to start
                waiter = ec2.get_waiter('instance_running')
                waiter.wait(InstanceIds=instance_ids)
                
                # Update usage
                count = len(instance_ids)
                self.usage_counter.increment_renewals(count)
                self.usage_reporter.report_usage(
                    self.license_key,
                    'renew_ips',
                    {'count': count, 'region': self.region}
                )
                
                self.master.after(0, lambda: self.handle_renew_result(True, None, loading, count))
            except Exception as e:
                self.master.after(0, lambda: self.handle_renew_result(False, str(e), loading, 0))
        
        thread = threading.Thread(target=renew, daemon=True)
        thread.start()
    
    def handle_renew_result(self, success, error, loading, count):
        """Handle IP renewal result"""
        loading.close()
        
        if success:
            self.log("SUCCESS", f"Successfully renewed IPs for {count} instance(s) using STOP→START method")
            messagebox.showinfo("Success", f"Successfully renewed IPs for {count} instance(s)!")
            self.refresh_instances()
        else:
            self.log("ERROR", f"Failed to renew IPs: {error}")
            messagebox.showerror("Error", f"Failed to renew IPs:\n{error}")
    
    def renew_selected_ip(self):
        """Renew IP for selected instance using STOP→START method"""
        selection = self.instances_tree.selection()
        if not selection:
            return
        
        item = self.instances_tree.item(selection[0])
        instance_id = item['values'][0]
        
        if not messagebox.askyesno("Confirm", f"Renew IP for instance {instance_id}?\nThis will STOP and START the instance, changing its public IP."):
            return
        
        loading = LoadingDialog(
            self.master,
            "Renewing IP",
            f"Renewing IP for instance {instance_id} using STOP→START method..."
        )
        
        def renew():
            try:
                ec2 = boto3.client(
                    'ec2',
                    aws_access_key_id=self.aws_access_key,
                    aws_secret_access_key=self.aws_secret_key,
                    region_name=self.region
                )
                
                # Stop instance
                self.master.after(0, lambda: loading.update_status("Stopping instance..."))
                ec2.stop_instances(InstanceIds=[instance_id])
                
                # Wait for instance to stop
                waiter = ec2.get_waiter('instance_stopped')
                waiter.wait(InstanceIds=[instance_id])
                
                # Start instance
                self.master.after(0, lambda: loading.update_status("Starting instance..."))
                ec2.start_instances(InstanceIds=[instance_id])
                
                # Wait for instance to start
                waiter = ec2.get_waiter('instance_running')
                waiter.wait(InstanceIds=[instance_id])
                
                # Update usage
                self.usage_counter.increment_renewals(1)
                self.usage_reporter.report_usage(
                    self.license_key,
                    'renew_ip',
                    {'instance_id': instance_id, 'region': self.region}
                )
                
                self.master.after(0, lambda: self.handle_renew_single_result(True, None, loading, instance_id))
            except Exception as e:
                self.master.after(0, lambda: self.handle_renew_single_result(False, str(e), loading, instance_id))
        
        thread = threading.Thread(target=renew, daemon=True)
        thread.start()
    
    def handle_renew_single_result(self, success, error, loading, instance_id):
        """Handle single IP renewal result"""
        loading.close()
        
        if success:
            self.log("SUCCESS", f"Successfully renewed IP for instance {instance_id} using STOP→START method")
            messagebox.showinfo("Success", f"Successfully renewed IP for instance {instance_id}!")
            self.refresh_instances()
        else:
            self.log("ERROR", f"Failed to renew IP for {instance_id}: {error}")
            messagebox.showerror("Error", f"Failed to renew IP:\n{error}")
    
    def terminate_all_instances(self):
        """Terminate all instances"""
        if not self.instances:
            messagebox.showwarning("Warning", "No instances found")
            return
        
        if not messagebox.askyesno("Confirm", "Terminate ALL instances?\nThis action cannot be undone!"):
            return
        
        loading = LoadingDialog(
            self.master,
            "Terminating Instances",
            "Terminating all instances..."
        )
        
        def terminate():
            try:
                ec2 = boto3.client(
                    'ec2',
                    aws_access_key_id=self.aws_access_key,
                    aws_secret_access_key=self.aws_secret_key,
                    region_name=self.region
                )
                
                instance_ids = [inst['id'] for inst in self.instances]
                
                # Terminate instances
                ec2.terminate_instances(InstanceIds=instance_ids)
                
                count = len(instance_ids)
                
                self.master.after(0, lambda: self.handle_terminate_result(True, None, loading, count))
            except Exception as e:
                self.master.after(0, lambda: self.handle_terminate_result(False, str(e), loading, 0))
        
        thread = threading.Thread(target=terminate, daemon=True)
        thread.start()
    
    def handle_terminate_result(self, success, error, loading, count):
        """Handle termination result"""
        loading.close()
        
        if success:
            self.log("SUCCESS", f"Successfully terminated {count} instance(s)")
            messagebox.showinfo("Success", f"Successfully terminated {count} instance(s)!")
            self.refresh_instances()
        else:
            self.log("ERROR", f"Failed to terminate instances: {error}")
            messagebox.showerror("Error", f"Failed to terminate instances:\n{error}")
    
    def terminate_selected_instance(self):
        """Terminate selected instance"""
        selection = self.instances_tree.selection()
        if not selection:
            return
        
        item = self.instances_tree.item(selection[0])
        instance_id = item['values'][0]
        
        if not messagebox.askyesno("Confirm", f"Terminate instance {instance_id}?\nThis action cannot be undone!"):
            return
        
        try:
            ec2 = boto3.client(
                'ec2',
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
                region_name=self.region
            )
            
            ec2.terminate_instances(InstanceIds=[instance_id])
            
            self.log("SUCCESS", f"Successfully terminated instance {instance_id}")
            messagebox.showinfo("Success", f"Successfully terminated instance {instance_id}!")
            self.refresh_instances()
        
        except Exception as e:
            self.log("ERROR", f"Failed to terminate instance: {str(e)}")
            messagebox.showerror("Error", f"Failed to terminate instance:\n{str(e)}")
    
    def export_proxies(self):
        """Export proxy list to file"""
        if not self.instances:
            messagebox.showwarning("Warning", "No instances to export")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if not filename:
            return
        
        try:
            with open(filename, 'w') as f:
                for inst in self.instances:
                    if inst['ip'] != 'N/A' and inst['state'] == 'running':
                        f.write(f"{inst['ip']}:3128\n")
            
            self.log("SUCCESS", f"Exported {len(self.instances)} proxy(ies) to {filename}")
            messagebox.showinfo("Success", f"Exported proxy list to:\n{filename}")
        
        except Exception as e:
            self.log("ERROR", f"Failed to export proxies: {str(e)}")
            messagebox.showerror("Error", f"Failed to export proxies:\n{str(e)}")
    
    def show_instance_menu(self, event):
        """Show context menu for instance"""
        try:
            self.instances_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.instances_menu.grab_release()
    
    def copy_selected_ip(self):
        """Copy selected instance IP to clipboard"""
        selection = self.instances_tree.selection()
        if not selection:
            return
        
        item = self.instances_tree.item(selection[0])
        ip = item['values'][1]
        
        if ip != 'N/A':
            self.master.clipboard_clear()
            self.master.clipboard_append(f"{ip}:3128")
            self.log("INFO", f"Copied {ip}:3128 to clipboard")
    
    # Logging Methods
    
    def log(self, level, message):
        """Add log entry"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}\n"
        
        self.log_text.insert(tk.END, log_entry, level)
        self.log_text.see(tk.END)
    
    def clear_logs(self):
        """Clear log display"""
        if messagebox.askyesno("Confirm", "Clear all logs?"):
            self.log_text.delete(1.0, tk.END)
    
    def save_logs(self):
        """Save logs to file"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if not filename:
            return
        
        try:
            with open(filename, 'w') as f:
                f.write(self.log_text.get(1.0, tk.END))
            
            messagebox.showinfo("Success", f"Logs saved to:\n{filename}")
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save logs:\n{str(e)}")
    
    # Statistics Methods
    
    def refresh_statistics(self):
        """Refresh statistics display"""
        stats = self.usage_counter.get_stats()
        
        for key, label in self.stats_labels.items():
            value = stats.get(key, 0)
            
            if key in ['first_used', 'last_used'] and value:
                try:
                    dt = datetime.fromisoformat(value)
                    value = dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    pass
            
            label.config(text=str(value))
    
    # Configuration Methods
    
    def load_config(self):
        """Load configuration from file"""
        if not os.path.exists(self.config_file):
            return
        
        try:
            config = configparser.ConfigParser()
            config.read(self.config_file)
            
            if 'License' in config:
                self.license_key = config['License'].get('key', '')
            
            if 'AWS' in config:
                self.aws_access_key = config['AWS'].get('access_key', '')
                self.aws_secret_key = config['AWS'].get('secret_key', '')
                self.region = config['AWS'].get('region', 'us-east-1')
        
        except Exception as e:
            self.log("ERROR", f"Failed to load configuration: {str(e)}")
    
    def save_config(self):
        """Save configuration to file"""
        try:
            config = configparser.ConfigParser()
            
            config['License'] = {
                'key': self.license_key
            }
            
            config['AWS'] = {
                'access_key': self.aws_access_key,
                'secret_key': self.aws_secret_key,
                'region': self.region
            }
            
            with open(self.config_file, 'w') as f:
                config.write(f)
        
        except Exception as e:
            self.log("ERROR", f"Failed to save configuration: {str(e)}")

def main():
    root = tk.Tk()
    app = AWSProxyGenerator(root)
    root.mainloop()

if __name__ == "__main__":
    main()
