import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
import socket
import ssl
import os
import hashlib
import threading
import time
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import datetime
import json
from datetime import datetime, timedelta
import queue
from cryptography.fernet import Fernet
import base64

# Configuration
BUFFER_SIZE = 4096
DEFAULT_PORT = 8443
CERT_EXPIRY_DAYS = 365
RATE_LIMIT_BYTES = 1024 * 1024 * 10  # 10 MB/s
TRANSFER_TIMEOUT = 30  # seconds
MAX_RETRIES = 3

class RateLimiter:
    def __init__(self, rate_limit_bytes):
        self.rate_limit = rate_limit_bytes
        self.transferred = 0
        self.last_check = time.time()

    def can_transfer(self, bytes_count):
        current_time = time.time()
        time_passed = current_time - self.last_check
        
        if time_passed >= 1.0:
            self.transferred = 0
            self.last_check = current_time
        
        if self.transferred + bytes_count <= self.rate_limit:
            self.transferred += bytes_count
            return True
        return False

class SecureSettings:
    def __init__(self):
        self.key = self._get_or_create_key()
        self.cipher = Fernet(self.key)
    
    def _get_or_create_key(self):
        key_file = "settings.key"
        if os.path.exists(key_file):
            with open(key_file, "rb") as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, "wb") as f:
                f.write(key)
            return key
    
    def save_settings(self, data):
        encrypted = self.cipher.encrypt(json.dumps(data).encode())
        with open("settings.enc", "wb") as f:
            f.write(encrypted)
    
    def load_settings(self):
        try:
            with open("settings.enc", "rb") as f:
                encrypted = f.read()
            decrypted = self.cipher.decrypt(encrypted)
            return json.loads(decrypted)
        except Exception:
            return {}

class FileTransferApp:
    def __init__(self):
        self.root = TkinterDnD.Tk()
        self.root.title("Secure P2P File Transfer")
        self.root.geometry("700x500")
        
        # Initialize file paths
        self.file_path = None
        self.save_path = None
        
        # Use a native Windows theme if available
        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use("vista")
        except Exception:
            self.style.theme_use("clam")
        
        self.transfer_active = False
        self.current_progress = 0
        self.transfer_history = []
        self.secure_settings = SecureSettings()
        
        # Generate certificates BEFORE UI creation
        self.generate_certificates()
        
        # Now create the UI components
        self.create_widgets()
        
        # Create a status bar for feedback
        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w")
        self.status_bar.pack(side="bottom", fill="x", padx=2, pady=2)
        
        self.load_saved_settings()

        # Create custom styles for progress bars
        self.style.configure("Red.Horizontal.TProgressbar", 
                             background="red", thickness=20)
        self.style.configure("Yellow.Horizontal.TProgressbar", 
                             background="orange", thickness=20)
        self.style.configure("Green.Horizontal.TProgressbar", 
                             background="green", thickness=20)
        
        # Create connection status indicator and start checking for peers
        self.connection_frame = ttk.Frame(self.root)
        self.connection_frame.pack(side="bottom", fill="x", before=self.status_bar)
        
        self.connection_indicator = ttk.Label(
            self.connection_frame, text="●", foreground="red", font=("Arial", 12)
        )
        self.connection_indicator.pack(side="left", padx=5)
        
        self.connection_status = ttk.Label(
            self.connection_frame, text="Disconnected"
        )
        self.connection_status.pack(side="left")
        
        # Set up a periodic check for peer availability
        self.root.after(1000, self.check_peer_availability)

    def create_widgets(self):
        self.notebook = ttk.Notebook(self.root)
        
        # Quick Connect Tab (New)
        connect_frame = ttk.Frame(self.notebook, padding=10)
        self.create_quick_connect_ui(connect_frame)
        
        # Sender Tab
        sender_frame = ttk.Frame(self.notebook, padding=10)
        self.create_sender_ui(sender_frame)
        
        # Receiver Tab
        receiver_frame = ttk.Frame(self.notebook, padding=10)
        self.create_receiver_ui(receiver_frame)
        
        # Settings Tab
        settings_frame = ttk.Frame(self.notebook, padding=10)
        self.create_settings_ui(settings_frame)
        
        # History Tab
        history_frame = ttk.Frame(self.notebook, padding=10)
        self.create_history_tab(history_frame)
        
        self.notebook.add(connect_frame, text="Quick Connect")
        self.notebook.add(sender_frame, text="Sender")
        self.notebook.add(receiver_frame, text="Receiver")
        self.notebook.add(settings_frame, text="Settings")
        self.notebook.add(history_frame, text="History")
        
        self.notebook.pack(expand=True, fill="both", padx=5, pady=5)

    def create_quick_connect_ui(self, parent):
        """Create a simplified connection UI for easy peer connection"""
        # Connection code section
        connection_frame = ttk.LabelFrame(parent, text="Your Connection Info", padding=10)
        connection_frame.grid(row=0, column=0, padx=5, pady=10, sticky="nsew", columnspan=2)
        
        # Get and display connection code
        self.connection_code = self.generate_connection_code()
        code_frame = ttk.Frame(connection_frame)
        code_frame.pack(fill="x", expand=True, pady=10)
        
        self.code_display = ttk.Label(code_frame, text=self.connection_code, font=("Arial", 16))
        self.code_display.pack(side="left", padx=10)
        
        ttk.Button(code_frame, text="Copy", command=self.copy_connection_code).pack(side="left", padx=5)
        ttk.Button(code_frame, text="Refresh", command=self.refresh_connection_code).pack(side="left")
        
        # Show QR code for mobile scanning
        try:
            import qrcode
            from PIL import ImageTk, Image
            import io
            
            # Generate QR code for connection info
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            connection_info = f"p2pft://{self.connection_code}"
            qr.add_data(connection_info)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            
            # Convert to PhotoImage and display
            qr_image = ImageTk.PhotoImage(Image.open(buffer))
            qr_label = ttk.Label(connection_frame, image=qr_image)
            qr_label.image = qr_image  # Keep a reference
            qr_label.pack(pady=10)
        except ImportError:
            ttk.Label(connection_frame, text="Install qrcode and Pillow packages for QR code generation").pack(pady=10)
        
        # Connect to peer section
        connect_to_frame = ttk.LabelFrame(parent, text="Connect to Peer", padding=10)
        connect_to_frame.grid(row=1, column=0, padx=5, pady=10, sticky="nsew", columnspan=2)
        
        ttk.Label(connect_to_frame, text="Enter connection code:").pack(anchor="w", pady=5)
        
        code_entry_frame = ttk.Frame(connect_to_frame)
        code_entry_frame.pack(fill="x", expand=True, pady=5)
        
        self.peer_code_entry = ttk.Entry(code_entry_frame, width=40, font=("Arial", 12))
        self.peer_code_entry.pack(side="left", padx=5, fill="x", expand=True)
        
        ttk.Button(code_entry_frame, text="Paste", 
                   command=lambda: self.peer_code_entry.delete(0, tk.END) or self.peer_code_entry.insert(0, self.root.clipboard_get())
                  ).pack(side="left", padx=5)
        
        ttk.Button(connect_to_frame, text="Connect", command=self.connect_to_peer).pack(pady=10)
        
        # Saved peers section
        peers_frame = ttk.LabelFrame(parent, text="Saved Peers", padding=10)
        peers_frame.grid(row=2, column=0, padx=5, pady=10, sticky="nsew", columnspan=2)
        
        # Create a treeview to display saved peers
        columns = ("name", "last_connected", "status")
        self.peers_tree = ttk.Treeview(peers_frame, columns=columns, show="headings", height=5)
        
        self.peers_tree.heading("name", text="Name")
        self.peers_tree.heading("last_connected", text="Last Connected")
        self.peers_tree.heading("status", text="Status")
        
        self.peers_tree.column("name", width=150)
        self.peers_tree.column("last_connected", width=150)
        self.peers_tree.column("status", width=100)
        
        self.peers_tree.pack(fill="both", expand=True, pady=5)
        
        # Buttons for peer management
        peers_button_frame = ttk.Frame(peers_frame)
        peers_button_frame.pack(fill="x", pady=5)
        
        ttk.Button(peers_button_frame, text="Connect", command=self.connect_to_selected_peer).pack(side="left", padx=5)
        ttk.Button(peers_button_frame, text="Remove", command=self.remove_selected_peer).pack(side="left", padx=5)
        ttk.Button(peers_button_frame, text="Add New", command=self.add_new_peer).pack(side="left", padx=5)
        
        # Configure grid weights
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)
        
        # Load saved peers
        self.load_saved_peers()

    def generate_connection_code(self):
        """Generate a user-friendly connection code containing IP and fingerprint"""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        except Exception:
            local_ip = "127.0.0.1"
        finally:
            s.close()
        
        # Get first 8 characters of fingerprint for shorter code
        short_fingerprint = self.get_cert_fingerprint()[:8]
        
        # Combine IP, port and shortened fingerprint into connection code
        return f"{local_ip}:{DEFAULT_PORT}:{short_fingerprint}"

    def copy_connection_code(self):
        """Copy connection code to clipboard"""
        self.root.clipboard_clear()
        self.root.clipboard_append(self.connection_code)
        self.status_var.set("Connection code copied to clipboard!")

    def refresh_connection_code(self):
        """Refresh the connection code"""
        self.connection_code = self.generate_connection_code()
        self.code_display.config(text=self.connection_code)
        self.status_var.set("Connection code refreshed")

    def connect_to_peer(self):
        """Connect to a peer using their connection code"""
        code = self.peer_code_entry.get().strip()
        if not code:
            messagebox.showerror("Error", "Please enter a connection code")
            return
        
        try:
            parts = code.split(":")
            if len(parts) != 3:
                raise ValueError("Invalid connection code format")
            
            ip, port, fingerprint = parts
            port = int(port)
            
            # Set values in receiver tab
            self.sender_ip.delete(0, tk.END)
            self.sender_ip.insert(0, ip)
            
            self.port.delete(0, tk.END)
            self.port.insert(0, str(port))
            
            self.fingerprint.delete(0, tk.END)
            self.fingerprint.insert(0, fingerprint)
            
            # Switch to receiver tab
            self.notebook.select(2)  # Index of receiver tab
            
            self.status_var.set(f"Ready to connect to {ip}")
        except Exception as e:
            messagebox.showerror("Invalid Connection Code", str(e))

    def save_peer(self, name, ip, port, fingerprint):
        """Save a peer to the peers list"""
        settings = self.secure_settings.load_settings()
        peers = settings.get("saved_peers", [])
        
        # Check if peer already exists by name
        for i, peer in enumerate(peers):
            if peer["name"] == name:
                # Update existing peer
                peers[i] = {
                    "name": name,
                    "ip": ip,
                    "port": port,
                    "fingerprint": fingerprint,
                    "last_connected": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                break
        else:
            # Add new peer
            peers.append({
                "name": name,
                "ip": ip,
                "port": port,
                "fingerprint": fingerprint,
                "last_connected": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        
        settings["saved_peers"] = peers
        self.secure_settings.save_settings(settings)
        self.load_saved_peers()  # Refresh the list

    def load_saved_peers(self):
        """Load saved peers into the peers tree"""
        # Clear existing entries
        self.peers_tree.delete(*self.peers_tree.get_children())
        
        # Load from settings
        settings = self.secure_settings.load_settings()
        peers = settings.get("saved_peers", [])
        
        for peer in peers:
            self.peers_tree.insert("", "end", values=(
                peer["name"],
                peer.get("last_connected", "Never"),
                "Offline"  # Default status
            ))

    def connect_to_selected_peer(self):
        """Connect to the selected peer from the peers list"""
        selected = self.peers_tree.selection()
        if not selected:
            messagebox.showinfo("Selection Required", "Please select a peer to connect to")
            return
        
        # Get the name of the selected peer
        peer_name = self.peers_tree.item(selected[0])["values"][0]
        
        # Find the peer in settings
        settings = self.secure_settings.load_settings()
        peers = settings.get("saved_peers", [])

    def remove_selected_peer(self):
        """Remove the selected peer from the saved peers list"""
        selected = self.peers_tree.selection()
        if not selected:
            messagebox.showinfo("Selection Required", "Please select a peer to remove")
            return
        
        # Get the name of the selected peer
        peer_name = self.peers_tree.item(selected[0])["values"][0]
        
        # Confirm deletion
        if not messagebox.askyesno("Confirm Deletion", f"Are you sure you want to remove '{peer_name}'?"):
            return
        
        # Find the peer in settings and remove it
        settings = self.secure_settings.load_settings()
        peers = settings.get("saved_peers", [])
        
        # Filter out the selected peer
        peers = [peer for peer in peers if peer["name"] != peer_name]
        
        # Update settings
        settings["saved_peers"] = peers
        self.secure_settings.save_settings(settings)
        
        # Refresh the list
        self.load_saved_peers()
        self.status_var.set(f"Removed peer: {peer_name}")

    def add_new_peer(self):
        """Show dialog to manually add a new peer"""
        # Create a top-level window for the dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Add New Peer")
        dialog.geometry("400x250")
        dialog.resizable(False, False)
        dialog.transient(self.root)  # Make dialog modal
        dialog.grab_set()
        
        # Add form fields with labels
        ttk.Label(dialog, text="Peer Name:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        name_entry = ttk.Entry(dialog, width=30)
        name_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        
        ttk.Label(dialog, text="IP Address:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        ip_entry = ttk.Entry(dialog, width=30)
        ip_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        
        ttk.Label(dialog, text="Port:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        port_entry = ttk.Entry(dialog, width=30)
        port_entry.insert(0, str(DEFAULT_PORT))
        port_entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew")
        
        ttk.Label(dialog, text="Fingerprint:").grid(row=3, column=0, padx=10, pady=10, sticky="w")
        fingerprint_entry = ttk.Entry(dialog, width=30)
        fingerprint_entry.grid(row=3, column=1, padx=10, pady=10, sticky="ew")
        
        def save_peer_callback():
            # Validate inputs
            name = name_entry.get().strip()
            ip = ip_entry.get().strip()
            port = port_entry.get().strip()
            fingerprint = fingerprint_entry.get().strip()
            
            if not name or not ip or not port or not fingerprint:
                messagebox.showerror("Validation Error", "All fields are required", parent=dialog)
                return
                
            try:
                port = int(port)
            except ValueError:
                messagebox.showerror("Validation Error", "Port must be a number", parent=dialog)
                return
                
            # Save the peer
            self.save_peer(name, ip, port, fingerprint)
            
            # Close the dialog
            dialog.destroy()
            
            # Show confirmation message
            self.status_var.set(f"Added new peer: {name}")
            
        # Add buttons
        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=4, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Save", command=save_peer_callback).pack(side="left", padx=10)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side="left", padx=10)
        
        # Configure grid weights
        dialog.columnconfigure(1, weight=1)
        
        # Focus on the first field
        name_entry.focus_set()

    def create_sender_ui(self, parent):
        # Use grid layout for a more organized UI
        ttk.Button(parent, text="Select File", command=self.select_file)\
            .grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Button(parent, text="Select Multiple", command=self.select_multiple_files)\
            .grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.selected_file_label = ttk.Label(parent, text="No file selected")
        self.selected_file_label.grid(row=0, column=2, padx=5, pady=5, sticky="w")
        
        ttk.Label(parent, text="Connection Info:")\
            .grid(row=1, column=0, columnspan=2, pady=5, sticky="w")
        self.info_text = tk.Text(parent, height=5, width=50)
        self.info_text.grid(row=2, column=0, columnspan=2, padx=5, pady=5)
        
        self.progress = ttk.Progressbar(parent, orient="horizontal", length=300, mode="determinate")
        self.progress.grid(row=3, column=0, columnspan=2, pady=10)
        self.eta_label = ttk.Label(parent, text="ETA: 0s")
        self.eta_label.grid(row=4, column=0, padx=5, pady=5, sticky="w")
        ttk.Button(parent, text="Start Transfer", command=self.start_sender)\
            .grid(row=4, column=1, padx=5, pady=5, sticky="e")
        
        # Drop files frame with a sunken border to hint drag/drop area
        self.drop_frame = ttk.LabelFrame(parent, text="➕ \nDrag & Drop Here", padding=10)
        self.drop_frame.grid(row=5, column=0, columnspan=2, pady=10, sticky="nsew")
        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind('<<Drop>>', self.handle_drop)
        
        self.pause_button = ttk.Button(parent, text="Pause", command=self.toggle_pause)
        self.pause_button.grid(row=6, column=0, padx=5, pady=5, sticky="w")
        
        self.encryption_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(parent, text="Enable encryption", variable=self.encryption_var)\
            .grid(row=6, column=1, padx=5, pady=5, sticky="e")
        
        # Add files list
        files_frame = ttk.LabelFrame(parent, text="Selected Files", padding=10)
        files_frame.grid(row=7, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        
        # Create a listbox for multiple files
        self.files_listbox = tk.Listbox(files_frame, height=5, width=40)
        self.files_listbox.pack(side="left", fill="both", expand=True)
        
        # Add scrollbar for files list
        files_scrollbar = ttk.Scrollbar(files_frame, orient="vertical", command=self.files_listbox.yview)
        self.files_listbox.configure(yscrollcommand=files_scrollbar.set)
        files_scrollbar.pack(side="right", fill="y")
        
        # Configure grid weight for the drop_frame area
        parent.rowconfigure(5, weight=1)
        parent.columnconfigure(1, weight=1)

    def create_receiver_ui(self, parent):
        # Layout with grid for consistency
        ttk.Label(parent, text="Sender IP:")\
            .grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.sender_ip = ttk.Entry(parent)
        self.sender_ip.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        ttk.Label(parent, text="Port:")\
            .grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.port = ttk.Entry(parent)
        self.port.insert(0, str(DEFAULT_PORT))
        self.port.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        ttk.Label(parent, text="Fingerprint:")\
            .grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.fingerprint = ttk.Entry(parent)
        self.fingerprint.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        
        ttk.Button(parent, text="Save Location", command=self.select_save_path)\
            .grid(row=3, column=0, padx=5, pady=10, sticky="w")
        self.save_path_label = ttk.Label(parent, text="No save location selected")
        self.save_path_label.grid(row=3, column=1, padx=5, pady=10, sticky="w")
        
        self.receiver_progress = ttk.Progressbar(parent, orient="horizontal", length=300, mode="determinate")
        self.receiver_progress.grid(row=4, column=0, columnspan=2, padx=5, pady=10)
        ttk.Button(parent, text="Start Receive", command=self.start_receiver)\
            .grid(row=5, column=0, columnspan=2, padx=5, pady=10)
        
        parent.columnconfigure(1, weight=1)

    def create_settings_ui(self, parent):
        # General settings frame
        general_frame = ttk.LabelFrame(parent, text="General Settings", padding=10)
        general_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        
        # Default save path
        ttk.Label(general_frame, text="Default Save Path:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.default_save_path_var = tk.StringVar()
        ttk.Entry(general_frame, textvariable=self.default_save_path_var, width=30).grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(general_frame, text="Browse", command=self.set_default_save_path).grid(row=0, column=2, sticky="w", padx=5, pady=5)
        
        # Transfer settings
        transfer_frame = ttk.LabelFrame(parent, text="Transfer Settings", padding=10)
        transfer_frame.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        
        # Rate limit
        ttk.Label(transfer_frame, text="Rate Limit (MB/s):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.rate_limit_var = tk.StringVar(value="10")
        ttk.Spinbox(transfer_frame, from_=1, to=100, textvariable=self.rate_limit_var, width=5).grid(row=0, column=1, sticky="w", padx=5, pady=5)
        
        # Security settings
        security_frame = ttk.LabelFrame(parent, text="Security Settings", padding=10)
        security_frame.grid(row=2, column=0, padx=5, pady=5, sticky="ew")
        
        # Always verify fingerprint
        self.verify_fingerprint_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(security_frame, text="Always verify fingerprint", variable=self.verify_fingerprint_var).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        
        # Enable compression
        self.compression_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(security_frame, text="Enable compression", variable=self.compression_var).grid(row=1, column=0, sticky="w", padx=5, pady=5)
        
        # Save button
        ttk.Button(parent, text="Save Settings", command=self.save_settings).grid(row=3, column=0, pady=15)
        
        # Configure grid weights
        parent.columnconfigure(0, weight=1)

    def set_default_save_path(self):
        path = filedialog.askdirectory()
        if path:
            self.default_save_path_var.set(path)

    def save_settings(self):
        settings = {
            "default_save_path": self.default_save_path_var.get(),
            "rate_limit": float(self.rate_limit_var.get()) * 1024 * 1024,  # Convert to bytes
            "verify_fingerprint": self.verify_fingerprint_var.get(),
            "compression": self.compression_var.get(),
            "transfer_history": self.transfer_history
        }
        self.secure_settings.save_settings(settings)
        messagebox.showinfo("Settings", "Settings saved successfully")

    def load_saved_settings(self):
        settings = self.secure_settings.load_settings()
        if settings:
            self.default_save_path_var.set(settings.get("default_save_path", ""))
            rate_limit_mb = settings.get("rate_limit", 10 * 1024 * 1024) / (1024 * 1024)
            self.rate_limit_var.set(str(int(rate_limit_mb)))
            self.verify_fingerprint_var.set(settings.get("verify_fingerprint", True))
            self.compression_var.set(settings.get("compression", False))
            self.transfer_history = settings.get("transfer_history", [])

    def generate_certificates(self):
        if not os.path.exists("sender_cert.pem") or not os.path.exists("sender_key.pem"):
            key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, u"p2p-file-transfer"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"My Organization"),
                x509.NameAttribute(NameOID.COUNTRY_NAME, u"US"),
            ])
            cert = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.utcnow())
                .not_valid_after(datetime.utcnow() + timedelta(days=CERT_EXPIRY_DAYS))
                .add_extension(
                    x509.SubjectAlternativeName([x509.DNSName(u"localhost")]),
                    critical=False,
                )
                .sign(key, hashes.SHA256(), default_backend())
            )
            with open("sender_key.pem", "wb") as f:
                f.write(key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                ))
            with open("sender_cert.pem", "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))

    def get_cert_fingerprint(self):
        with open("sender_cert.pem", "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read(), default_backend())
        return hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()

    def select_file(self):
        self.file_path = filedialog.askopenfilename()
        if self.file_path:
            self.selected_file_label.config(text=os.path.basename(self.file_path))
            self.show_connection_info()

    def select_files(self):
        self.file_paths = filedialog.askopenfilenames()
        if self.file_paths:
            self.files_listbox.delete(0, tk.END)
            for path in self.file_paths:
                self.files_listbox.insert(tk.END, os.path.basename(path))

    def select_multiple_files(self):
        """Allow selecting multiple files for transfer"""
        file_paths = filedialog.askopenfilenames()
        if not file_paths:
            return
            
        # Store the first file as the main file_path and keep all in a list
        self.file_paths = file_paths
        self.file_path = file_paths[0] if file_paths else None
        
        # Update the UI to show the number of selected files
        if len(file_paths) == 1:
            self.selected_file_label.config(text=os.path.basename(self.file_path))
        else:
            self.selected_file_label.config(text=f"{len(file_paths)} files selected")
        
        # Update connection info
        self.show_connection_info()

    def show_connection_info(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        except Exception:
            local_ip = "127.0.0.1"
        finally:
            s.close()
        
        info = f"IP: {local_ip}\nPort: {DEFAULT_PORT}\nFingerprint: {self.get_cert_fingerprint()}"
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(tk.END, info)

    def start_sender(self):
        if not self.file_path or not os.path.exists(self.file_path):
            messagebox.showerror("Error", "Please select a valid file first")
            return
        
        self.progress["value"] = 0
        threading.Thread(target=self.run_sender, daemon=True).start()

    def calculate_checksum(self, file_path):
        """Calculate SHA-256 checksum of file"""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            buf = f.read(BUFFER_SIZE)
            while buf:
                hasher.update(buf)
                buf = f.read(BUFFER_SIZE)
        return hasher.hexdigest()

    def run_sender(self):
        rate_limiter = RateLimiter(RATE_LIMIT_BYTES)
        retry_count = 0
        self.transfer_active = True  # Set to active when starting
        
        while retry_count < MAX_RETRIES:
            try:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain("sender_cert.pem", "sender_key.pem")
                context.minimum_version = ssl.TLSVersion.TLSv1_3  # Force TLS 1.3
                context.set_ciphers('ECDHE-RSA-AES256-GCM-SHA384')  # Use strong cipher suite
                
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(TRANSFER_TIMEOUT)
                    sock.bind(('0.0.0.0', DEFAULT_PORT))
                    sock.listen(1)
                    
                    # FIX: Accept connection on plain socket and then wrap it with SSL
                    conn, addr = sock.accept()
                    with context.wrap_socket(conn, server_side=True) as ssock:
                        # Add session token
                        session_token = os.urandom(32).hex()
                        ssock.sendall(session_token.encode())
                        
                        # Send file metadata
                        file_size = os.path.getsize(self.file_path)
                        
                        # Calculate checksum before sending
                        checksum = self.calculate_checksum(self.file_path)
                        metadata = {
                            "size": file_size,
                            "name": os.path.basename(self.file_path),
                            "timestamp": datetime.now().isoformat(),
                            "checksum": checksum
                        }
                        metadata_bytes = json.dumps(metadata).encode()
                        ssock.sendall(metadata_bytes)
                        
                        # Send file contents
                        with open(self.file_path, "rb") as f:
                            bytes_sent = 0
                            start_time = time.time()
                            while bytes_sent < file_size:
                                # Check if transfer is paused
                                while not self.transfer_active:
                                    time.sleep(0.1)  # Sleep while paused
                                    
                                chunk = f.read(BUFFER_SIZE)
                                if not chunk:
                                    break
                                    
                                # Rate limiting
                                while not rate_limiter.can_transfer(len(chunk)) and self.transfer_active:
                                    time.sleep(0.01)
                                    
                                ssock.sendall(chunk)
                                bytes_sent += len(chunk)
                                progress = (bytes_sent / file_size) * 100
                                self.root.after(0, self.update_progress, progress, bytes_sent, file_size, start_time)
                                
                # Add to history when transfer completes
                filename = os.path.basename(self.file_path)
                file_size = os.path.getsize(self.file_path)
                self.root.after(0, lambda: self.add_to_history(filename, file_size, "Sent"))
                break  # Transfer complete, exit retry loop
                
            except Exception as e:
                retry_count += 1
                # Ensure messagebox is called on the main thread
                self.root.after(0, lambda: messagebox.showerror("Transfer Error", str(e)))
                if retry_count >= MAX_RETRIES:
                    # Add failed transfer to history
                    if self.file_path:
                        filename = os.path.basename(self.file_path)
                        try:
                            file_size = os.path.getsize(self.file_path)
                        except:
                            file_size = 0
                        self.root.after(0, lambda: self.add_to_history(filename, file_size, "Sent", "Failed"))

    def update_progress(self, value, bytes_transferred, file_size, start_time):
        self.progress["value"] = value
        
        # Update the progress bar color based on progress
        if value < 25:
            self.progress.configure(style="Red.Horizontal.TProgressbar")
        elif value < 75:
            self.progress.configure(style="Yellow.Horizontal.TProgressbar")
        else:
            self.progress.configure(style="Green.Horizontal.TProgressbar")
        
        elapsed = time.time() - start_time
        if elapsed > 0 and bytes_transferred > 0:
            speed = bytes_transferred / elapsed  # bytes per second
            remaining_size = file_size - bytes_transferred
            
            if speed > 0:
                eta_seconds = remaining_size / speed
                speed_mb = speed / (1024 * 1024)
                
                # Format time nicely
                if eta_seconds < 60:
                    eta_text = f"{eta_seconds:.0f} seconds"
                elif eta_seconds < 3600:
                    eta_text = f"{eta_seconds/60:.1f} minutes"
                else:
                    eta_text = f"{eta_seconds/3600:.1f} hours"
                    
                self.eta_label.config(text=f"ETA: {eta_text} ({speed_mb:.2f} MB/s)")
                
                # Update status bar with transfer info
                percent = int(value)
                self.status_var.set(
                    f"Transferring: {self.format_size(bytes_transferred)} of {self.format_size(file_size)} "
                    f"({percent}%) at {speed_mb:.2f} MB/s"
                )

    def select_save_path(self):
        save_dir = filedialog.askdirectory()
        if save_dir:
            self.save_path = save_dir
            self.save_path_label.config(text=save_dir)

    def start_receiver(self):
        if not self.save_path:
            messagebox.showerror("Error", "Please select a save location first")
            return
        
        self.receiver_progress["value"] = 0
        threading.Thread(target=self.run_receiver, daemon=True).start()

    def run_receiver(self):
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.load_verify_locations("sender_cert.pem")
            context.minimum_version = ssl.TLSVersion.TLSv1_3  # Force TLS 1.3
            context.set_ciphers('ECDHE-RSA-AES256-GCM-SHA384')  # Use strong cipher suite
            
            with socket.create_connection((self.sender_ip.get(), int(self.port.get())), timeout=TRANSFER_TIMEOUT) as sock:
                with context.wrap_socket(sock, server_hostname="p2p-file-transfer") as ssock:
                    # Verify fingerprint
                    cert = ssock.getpeercert(binary_form=True)
                    fingerprint = hashlib.sha256(cert).hexdigest()
                    if fingerprint != self.fingerprint.get():
                        raise ValueError("Certificate fingerprint does not match")
                    
                    # Receive session token
                    session_token = ssock.recv(64).decode()
                    
                    # Receive file metadata
                    metadata_bytes = ssock.recv(BUFFER_SIZE)
                    metadata = json.loads(metadata_bytes.decode())
                    file_size = metadata["size"]
                    file_name = metadata["name"]
                    
                    # Receive file contents
                    save_path = os.path.join(self.save_path, file_name)
                    with open(save_path, "wb") as f:
                        bytes_received = 0
                        while bytes_received < file_size:
                            chunk = ssock.recv(BUFFER_SIZE)
                            if not chunk:
                                break
                            f.write(chunk)
                            bytes_received += len(chunk)
                            progress = (bytes_received / file_size) * 100
                            self.root.after(0, lambda: self.update_receiver_progress(progress))
                    
                    # After receiving the file
                    received_checksum = self.calculate_checksum(save_path)
                    if received_checksum != metadata["checksum"]:
                        self.root.after(0, lambda: messagebox.showerror(
                            "Verification Failed", 
                            "File may be corrupted. Checksums do not match."
                         ))
                        self.root.after(0, lambda: self.add_to_history(file_name, file_size, "Received", "Failed (Checksum)"))
                    else:
                        self.root.after(0, lambda: messagebox.showinfo(
                            "Transfer Complete", 
                            "File verified successfully."
                        ))
                        self.root.after(0, lambda: self.add_to_history(file_name, file_size, "Received"))
            
        except Exception as e:
            self.root.after(0, lambda err=e: messagebox.showerror("Receive Error", str(err)))
            # Try to get filename from metadata if available
            filename = "Unknown"
            filesize = 0
            self.root.after(0, lambda: self.add_to_history(filename, filesize, "Received", "Failed"))

    def update_receiver_progress(self, value):
        self.receiver_progress["value"] = value

    def handle_drop(self, event):
        """Improved drag and drop file handling with multiple file support"""
        # Strip curly braces and extra spaces
        files = event.data.strip('{}')
        
        # Windows returns paths with spaces in curly braces, need to parse carefully
        if os.name == 'nt':
            # Split by space but respect quoted paths
            file_paths = []
            current_path = ""
            in_quotes = False
            
            for char in files:
                if char == '"' and not current_path.endswith('\\'):
                    in_quotes = not in_quotes
                    current_path += char
                elif char == ' ' and not in_quotes:
                    if current_path:
                        file_paths.append(current_path.strip('"'))
                        current_path = ""
                else:
                    current_path += char
            
            if current_path:
                file_paths.append(current_path.strip('"'))
        else:
            # Unix systems typically use spaces as separators
            file_paths = files.split()
        
        if not file_paths:
            return
            
        # Store the file paths
        self.file_paths = file_paths
        self.file_path = file_paths[0] if file_paths else None
        
        # Update the UI
        if len(file_paths) == 1:
            self.selected_file_label.config(text=os.path.basename(self.file_path))
        else:
            self.selected_file_label.config(text=f"{len(file_paths)} files selected")
        
        # Update the files listbox
        self.files_listbox.delete(0, tk.END)
        for path in file_paths:
            self.files_listbox.insert(tk.END, os.path.basename(path))
        
        # Update connection info
        self.show_connection_info()
        self.status_var.set(f"Added {len(file_paths)} file(s)")

    def toggle_pause(self):
        self.transfer_active = not self.transfer_active
        self.pause_button.config(text="Resume" if not self.transfer_active else "Pause")
        if self.transfer_active:
            self.status_var.set("Transfer resumed")
        else:
            self.status_var.set("Transfer paused")
        
    def create_history_tab(self, parent):
        # Add columns and headers
        columns = ("timestamp", "filename", "size", "direction", "status")
        self.history_tree = ttk.Treeview(parent, columns=columns, show="headings")
        
        # Set column headings
        self.history_tree.heading("timestamp", text="Time")
        self.history_tree.heading("filename", text="Filename")
        self.history_tree.heading("size", text="Size")
        self.history_tree.heading("direction", text="Direction")
        self.history_tree.heading("status", text="Status")
        
        # Set column widths
        self.history_tree.column("timestamp", width=150)
        self.history_tree.column("filename", width=200)
        self.history_tree.column("size", width=80)
        self.history_tree.column("direction", width=80)
        self.history_tree.column("status", width=100)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack widgets
        self.history_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Clear history button
        ttk.Button(parent, text="Clear History", 
                   command=self.clear_history).pack(pady=10)
        
        # Load history from settings
        self.load_history()

    def add_to_history(self, filename, size, direction, status="Completed"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.history_tree.insert("", 0, values=(timestamp, filename, self.format_size(size), direction, status))
        # Also save to persistent storage
        self.transfer_history.append({
            "timestamp": timestamp,
            "filename": filename,
            "size": size,
            "direction": direction,
            "status": status
        })
        self.save_history()

    def format_size(self, size_bytes):
        # Convert bytes to human-readable format
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024 or unit == 'GB':
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024

    def save_history(self):
        settings = self.secure_settings.load_settings()
        settings["transfer_history"] = self.transfer_history
        self.secure_settings.save_settings(settings)

    def load_history(self):
        settings = self.secure_settings.load_settings()
        self.transfer_history = settings.get("transfer_history", [])
        for entry in self.transfer_history:
            self.history_tree.insert("", 0, values=(
                entry["timestamp"], 
                entry["filename"], 
                self.format_size(entry["size"]), 
                entry["direction"], 
                entry["status"]
            ))

    def clear_history(self):
        self.history_tree.delete(*self.history_tree.get_children())
        self.transfer_history = []
        self.save_history()

    def check_peer_availability(self):
        """Check if saved peers are available"""
        settings = self.secure_settings.load_settings()
        peers = settings.get("saved_peers", [])
        
        # Check only if we have the peers tree
        if hasattr(self, "peers_tree"):
            for item in self.peers_tree.get_children():
                peer_name = self.peers_tree.item(item)["values"][0]
                
                # Find this peer in our settings
                for peer in peers:
                    if peer["name"] == peer_name:
                        # Try to ping the peer
                        try:
                            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            sock.settimeout(0.5)  # Short timeout to not block the UI
                            result = sock.connect_ex((peer["ip"], int(peer["port"])))
                            sock.close()
                            
                            # Update the status in the tree view
                            if result == 0:
                                # Port is open, peer might be available
                                self.peers_tree.item(item, values=(
                                    peer_name, 
                                    peer.get("last_connected", "Never"),
                                    "Online"
                                ))
                            else:
                                self.peers_tree.item(item, values=(
                                    peer_name,
                                    peer.get("last_connected", "Never"),
                                    "Offline"
                                ))
                        except:
                            # In case of any error, mark as offline
                            self.peers_tree.item(item, values=(
                                peer_name,
                                peer.get("last_connected", "Never"),
                                "Offline"
                            ))
        
        # Schedule the next check
        self.root.after(10000, self.check_peer_availability)  # Check every 10 seconds

if __name__ == "__main__":
    app = FileTransferApp()
    app.root.mainloop()
