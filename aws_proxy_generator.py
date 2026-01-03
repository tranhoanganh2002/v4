import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import boto3
import requests
import threading
import time
import json
import os
from datetime import datetime
import uuid
import base64

class OnlineKeyValidator:
    def __init__(self):
        self.api_base = "https://your-api-endpoint.com"
        self.machine_id = self.get_machine_id()
    
    def get_machine_id(self):
        return str(uuid.getnode())
    
    def validate_key(self, key):
        try:
            response = requests.post(f"{self.api_base}/validate", 
                json={"key": key, "machine_id": self.machine_id},
                timeout=5)
            return response.json().get("valid", False)
        except:
            return False

class UsageCounter:
    def __init__(self, user_id):
        self.user_id = user_id
        self.count_file = f"usage_{user_id}.json"
        self.load_count()
    
    def load_count(self):
        try:
            with open(self.count_file, 'r') as f:
                data = json.load(f)
                self.count = data.get('count', 0)
        except:
            self.count = 0
    
    def increment(self):
        self.count += 1
        self.save_count()
    
    def save_count(self):
        with open(self.count_file, 'w') as f:
            json.dump({'count': self.count, 'user_id': self.user_id}, f)
    
    def get_count(self):
        return self.count

class UsageReporter:
    def __init__(self, api_base):
        self.api_base = api_base
    
    def report_usage(self, user_id, action, details=None):
        try:
            data = {
                "user_id": user_id,
                "action": action,
                "timestamp": datetime.now().isoformat(),
                "details": details
            }
            requests.post(f"{self.api_base}/report", json=data, timeout=5)
        except:
            pass

class LoadingDialog:
    def __init__(self, parent, title="Đang xử lý..."):
        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.geometry("300x100")
        self.top.transient(parent)
        self.top.grab_set()
        
        # Center the dialog
        self.top.update_idletasks()
        x = (self.top.winfo_screenwidth() // 2) - (300 // 2)
        y = (self.top.winfo_screenheight() // 2) - (100 // 2)
        self.top.geometry(f"300x100+{x}+{y}")
        
        self.label = tk.Label(self.top, text="Vui lòng đợi...", font=("Arial", 12))
        self.label.pack(pady=20)
        
        self.progress = ttk.Progressbar(self.top, mode='indeterminate')
        self.progress.pack(pady=10, padx=20, fill=tk.X)
        self.progress.start(10)
    
    def close(self):
        self.progress.stop()
        self.top.destroy()

class AWSProxyGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("AWS Proxy Manager - Quản lý Proxy AWS")
        self.root.geometry("1400x800")
        
        # Initialize validators and counters
        self.key_validator = OnlineKeyValidator()
        self.usage_reporter = UsageReporter("https://your-api-endpoint.com")
        
        self.instances = []
        self.instance_checkboxes = {}
        self.select_all_var = tk.BooleanVar()
        
        # Create main container
        main_container = tk.Frame(root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left panel for credentials
        left_panel = tk.LabelFrame(main_container, text="Thông tin AWS", padx=10, pady=10)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 5))
        
        # AWS Credentials
        tk.Label(left_panel, text="Access Key ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.ak_entry = tk.Entry(left_panel, width=40)
        self.ak_entry.grid(row=0, column=1, pady=5)
        
        tk.Label(left_panel, text="Secret Access Key:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.sk_entry = tk.Entry(left_panel, width=40, show="*")
        self.sk_entry.grid(row=1, column=1, pady=5)
        
        tk.Label(left_panel, text="Region:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.region_entry = tk.Entry(left_panel, width=40)
        self.region_entry.insert(0, "us-east-1")
        self.region_entry.grid(row=2, column=1, pady=5)
        
        # Proxy settings
        tk.Label(left_panel, text="Proxy Format:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.format_var = tk.StringVar(value="ip:port:user:pass")
        formats = ["ip:port:user:pass", "user:pass@ip:port", "ip:port"]
        format_menu = ttk.Combobox(left_panel, textvariable=self.format_var, values=formats, width=37)
        format_menu.grid(row=3, column=1, pady=5)
        
        tk.Label(left_panel, text="Port:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.port_entry = tk.Entry(left_panel, width=40)
        self.port_entry.insert(0, "3128")
        self.port_entry.grid(row=4, column=1, pady=5)
        
        tk.Label(left_panel, text="Username:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.user_entry = tk.Entry(left_panel, width=40)
        self.user_entry.insert(0, "proxyuser")
        self.user_entry.grid(row=5, column=1, pady=5)
        
        tk.Label(left_panel, text="Password:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.pass_entry = tk.Entry(left_panel, width=40)
        self.pass_entry.insert(0, "Pass123")
        self.pass_entry.grid(row=6, column=1, pady=5)
        
        # Buttons
        btn_frame = tk.Frame(left_panel)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=10)
        
        tk.Button(btn_frame, text="Lấy danh sách Instance", command=self.fetch_instances, 
                 bg="#4CAF50", fg="white", padx=10, pady=5).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Làm mới IP đã chọn", command=self.renew_selected, 
                 bg="#2196F3", fg="white", padx=10, pady=5).pack(side=tk.LEFT, padx=5)
        
        # Right panel for instances
        right_panel = tk.LabelFrame(main_container, text="Danh sách Instance", padx=10, pady=10)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Select all checkbox
        select_all_frame = tk.Frame(right_panel)
        select_all_frame.pack(fill=tk.X, pady=5)
        tk.Checkbutton(select_all_frame, text="Chọn tất cả", variable=self.select_all_var, 
                      command=self.toggle_select_all).pack(side=tk.LEFT)
        
        # Scrollable frame for instances
        canvas = tk.Canvas(right_panel)
        scrollbar = tk.Scrollbar(right_panel, orient="vertical", command=canvas.yview)
        self.scrollable_frame = tk.Frame(canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Status bar
        self.status_label = tk.Label(root, text="Sẵn sàng", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)
    
    def fetch_instances(self):
        ak = self.ak_entry.get().strip()
        sk = self.sk_entry.get().strip()
        reg = self.region_entry.get().strip()
        
        if not ak or not sk:
            messagebox.showerror("Lỗi", "Vui lòng nhập đầy đủ Access Key và Secret Key")
            return
        
        loading = LoadingDialog(self.root, "Đang tải danh sách Instance...")
        
        def fetch():
            try:
                ec2 = boto3.client('ec2', aws_access_key_id=ak, aws_secret_access_key=sk, region_name=reg)
                response = ec2.describe_instances()
                
                self.instances = []
                for reservation in response['Reservations']:
                    for instance in reservation['Instances']:
                        if instance['State']['Name'] == 'running':
                            inst_data = {
                                'id': instance['InstanceId'],
                                'public_ip': instance.get('PublicIpAddress', 'N/A'),
                                'private_ip': instance.get('PrivateIpAddress', 'N/A'),
                                'type': instance['InstanceType'],
                                'state': instance['State']['Name'],
                                'access_key': ak,
                                'secret_key': sk,
                                'region': reg,
                                'proxy_user': self.user_entry.get().strip(),
                                'proxy_pass': self.pass_entry.get().strip()
                            }
                            self.instances.append(inst_data)
                
                self.root.after(0, lambda: self.display_instances())
                self.root.after(0, lambda: self.status_label.config(text=f"Đã tải {len(self.instances)} instance"))
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Lỗi", f"Không thể lấy danh sách: {str(e)}"))
            finally:
                self.root.after(0, loading.close)
        
        thread = threading.Thread(target=fetch)
        thread.daemon = True
        thread.start()
    
    def display_instances(self):
        # Clear existing widgets
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        self.instance_checkboxes.clear()
        
        # Create checkboxes for each instance
        for idx, inst in enumerate(self.instances):
            frame = tk.Frame(self.scrollable_frame, relief=tk.RIDGE, borderwidth=1, padx=5, pady=5)
            frame.pack(fill=tk.X, padx=5, pady=2)
            
            var = tk.BooleanVar()
            cb = tk.Checkbutton(frame, variable=var)
            cb.pack(side=tk.LEFT)
            
            info_text = f"ID: {inst['id']} | IP: {inst['public_ip']} | Type: {inst['type']}"
            tk.Label(frame, text=info_text, font=("Arial", 9)).pack(side=tk.LEFT, padx=5)
            
            # Proxy display
            proxy_label = tk.Label(frame, text="", fg="blue", font=("Arial", 9))
            copy_btn = tk.Button(frame, text="Copy", command=None, padx=5, pady=2)
            
            self.instance_checkboxes[inst['id']] = {
                'var': var,
                'instance': inst,
                'frame': frame,
                'proxy_label': proxy_label,
                'copy_btn': copy_btn
            }
            
            # Initial proxy display
            if inst['public_ip'] != 'N/A':
                proxy = self.fmt_px(inst['public_ip'], self.format_var.get(), 
                                   inst['proxy_user'], inst['proxy_pass'])
                proxy_label.config(text=f"→ {proxy}")
                proxy_label.pack(side=tk.LEFT, padx=5)
                copy_btn.config(command=lambda p=proxy: self.copy_single_proxy(p))
                copy_btn.pack(side=tk.LEFT, padx=2)
    
    def toggle_select_all(self):
        state = self.select_all_var.get()
        for iid in self.instance_checkboxes:
            self.instance_checkboxes[iid]['var'].set(state)
    
    def fmt_px(self, ip, fmt, usr, pwd):
        port = self.port_entry.get().strip()
        if fmt == "ip:port:user:pass":
            return f"{ip}:{port}:{usr}:{pwd}"
        elif fmt == "user:pass@ip:port":
            return f"{usr}:{pwd}@{ip}:{port}"
        else:
            return f"{ip}:{port}"
    
    def copy_single_proxy(self, proxy):
        self.root.clipboard_clear()
        self.root.clipboard_append(proxy)
        self.status_label.config(text=f"Đã copy: {proxy}")
    
    def renew_selected(self):
        selected = []
        for iid, data in self.instance_checkboxes.items():
            if data['var'].get():
                selected.append((iid, data['instance']))
        
        if not selected:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 instance")
            return
        
        self.status_label.config(text=f"Đang làm mới {len(selected)} instance...")
        
        def renew_all():
            total = len(selected)
            for idx, (iid, inst) in enumerate(selected, 1):
                result = self.renew_single_elastic(
                    iid, inst['access_key'], inst['secret_key'], 
                    inst['region'], self.format_var.get(), idx, total
                )
                
                if result['ok']:
                    self.root.after(0, lambda r=result: self.status_label.config(
                        text=f"Làm mới thành công: {r['new_ip']}"))
                else:
                    self.root.after(0, lambda r=result: self.status_label.config(
                        text=f"Lỗi: {r['error']}"))
                
                time.sleep(1)
            
            self.root.after(0, lambda: self.status_label.config(text="Hoàn thành làm mới IP"))
        
        thread = threading.Thread(target=renew_all)
        thread.daemon = True
        thread.start()
    
    def renew_single_elastic(self, iid, ak, sk, reg, fi, idx, total):
        try:
            ec2 = boto3.client('ec2', aws_access_key_id=ak, aws_secret_access_key=sk, region_name=reg)
            
            # STOP instance
            ec2.stop_instances(InstanceIds=[iid])
            
            # Wait for instance to stop
            waiter = ec2.get_waiter('instance_stopped')
            waiter.wait(InstanceIds=[iid])
            
            # START instance
            ec2.start_instances(InstanceIds=[iid])
            
            # Wait for instance to start
            waiter = ec2.get_waiter('instance_running')
            waiter.wait(InstanceIds=[iid])
            
            # Get new IP
            inf = ec2.describe_instances(InstanceIds=[iid])
            instance = inf['Reservations'][0]['Instances'][0]
            new_ip = instance.get('PublicIpAddress')
            
            if not new_ip:
                raise Exception("Khong lay duoc IP moi")
            
            # Get proxy credentials from tags
            user = "proxyuser"
            password = "Pass123"
            if iid in self.instance_checkboxes:
                user = self.instance_checkboxes[iid]['instance'].get('proxy_user', 'proxyuser')
                password = self.instance_checkboxes[iid]['instance'].get('proxy_pass', 'Pass123')
            
            proxy = self.fmt_px(new_ip, fi, user, password)
            
            # Update UI
            if iid in self.instance_checkboxes:
                self.instance_checkboxes[iid]['instance']['public_ip'] = new_ip
                
                proxy_label = self.instance_checkboxes[iid].get('proxy_label')
                copy_btn = self.instance_checkboxes[iid].get('copy_btn')
                
                if proxy_label:
                    proxy_label.config(text=f"→ {proxy}")
                    proxy_label.pack(side=tk.LEFT, padx=5)
                
                if copy_btn:
                    copy_btn.config(command=lambda p=proxy: self.copy_single_proxy(p))
                    copy_btn.pack(side=tk.LEFT, padx=2)
            
            return {'ok': True, 'px': proxy, 'new_ip': new_ip}
            
        except Exception as e:
            return {'ok': False, 'error': str(e)}

def main():
    root = tk.Tk()
    app = AWSProxyGenerator(root)
    root.mainloop()

if __name__ == "__main__":
    main()
