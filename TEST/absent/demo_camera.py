"""
Absent Detection Module - Local Camera Demo (Improved)
Demo flow:
1. Capture face image using camera
2. Add demo person
3. Start detection (backend will open camera)
4. Show real-time status display (no camera preview to avoid conflict)

Improvements:
- Absent threshold changed to 10 seconds for quick demo
- Show real-time status in console and simple window
- Avoid camera conflict with backend
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import cv2
import numpy as np
import base64
import requests
import time
from datetime import datetime

# Config
BASE_URL = "http://localhost:8000/api/v1"
CAMERA_ID = 0  # Default camera
ABSENT_THRESHOLD_SEC = 10  # Absent threshold: 10 seconds

class CameraDemo:
    def __init__(self):
        self.cap = None
        self.is_running = False
        self.frame_count = 0
        
    def capture_face(self):
        """Capture face image"""
        print("\n[Camera] Preparing to capture face...")
        print("Please face the camera, press 'c' to capture, 'q' to quit")
        
        self.cap = cv2.VideoCapture(CAMERA_ID)
        if not self.cap.isOpened():
            print("[Error] Cannot open camera")
            return None
        
        # Set lower resolution for better performance
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        face_img = None
        
        while True:
            ret, frame = self.cap.read()
            if not ret:
                print("[Error] Cannot read camera frame")
                break
            
            # Display frame
            display_frame = frame.copy()
            h, w = display_frame.shape[:2]
            
            # Add hint text
            cv2.putText(display_frame, "Press 'c' to capture, 'q' to quit", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(display_frame, "Please face the camera", 
                       (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            
            # Show center box
            center_x, center_y = w // 2, h // 2
            cv2.rectangle(display_frame, 
                         (center_x - 100, center_y - 100), 
                         (center_x + 100, center_y + 100), 
                         (0, 255, 0), 2)
            
            cv2.imshow("Capture Face", display_frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('c'):
                face_img = frame.copy()
                print("[OK] Face image captured")
                break
            elif key == ord('q'):
                print("[Warning] User cancelled capture")
                break
        
        self.cap.release()
        cv2.destroyAllWindows()
        return face_img
    
    def add_demo_person(self, face_img):
        """Add demo person"""
        print("\n[Person] Adding demo person...")
        
        # Encode image
        _, buffer = cv2.imencode('.jpg', face_img)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        
        # Get current time, set duty period
        now = datetime.now()
        start_time = now.strftime("%H:%M")
        end_time = (now.replace(hour=now.hour + 2)).strftime("%H:%M")
        duty_period = f"{start_time}-{end_time}"
        
        person_data = {
            "person_id": "DEMO_PERSON_001",
            "name": "Demo Person",
            "post": "Demo Post",
            "duty_period": duty_period,
            "max_absent_min": 0.17,  # 10 seconds = 0.17 minutes
            "face_img": img_base64
        }
        
        response = requests.post(f"{BASE_URL}/absent/person/add", json=person_data)
        if response.status_code == 200:
            result = response.json()
            if "error" not in result:
                print(f"[OK] Person added: {result.get('person_id')}")
                print(f"   Duty Period: {duty_period}")
                print(f"   Absent Threshold: {ABSENT_THRESHOLD_SEC}s")
                return True
        
        print(f"[Error] Failed to add person: {response.text}")
        return False
    
    def add_camera_source(self):
        """Add camera video source"""
        print("\n[Source] Adding camera video source...")
        
        source_data = {
            "source_id": "DEMO_CAMERA_001",
            "source_name": "Demo Camera",
            "source_type": "camera",
            "device_id": CAMERA_ID
        }
        
        response = requests.post(f"{BASE_URL}/source/add", json=source_data)
        if response.status_code == 200:
            result = response.json()
            print(f"[OK] Video source added: DEMO_CAMERA_001")
            return True
        
        print(f"[Warning] Source may already exist or failed to add")
        return True
    
    def start_detection(self):
        """Start absent detection"""
        print("\n[Detection] Starting absent detection...")
        
        start_data = {"source_id": "DEMO_CAMERA_001"}
        response = requests.post(f"{BASE_URL}/absent/start", json=start_data)
        
        if response.status_code == 200:
            result = response.json()
            if "error" not in result:
                print("[OK] Detection started")
                self.is_running = True
                return True
        
        print(f"[Error] Failed to start: {response.text}")
        return False
    
    def get_status(self):
        """Get detection status"""
        try:
            response = requests.get(f"{BASE_URL}/absent/status", timeout=1)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None
    
    def get_alarms(self):
        """Get alarm records"""
        try:
            response = requests.get(f"{BASE_URL}/absent/alarm/list", timeout=1)
            if response.status_code == 200:
                return response.json().get('alarms', [])
        except:
            pass
        return []
    
    def create_status_image(self, status_data, alarms):
        """Create a status display image"""
        # Create a black image for status display
        img = np.zeros((400, 600, 3), dtype=np.uint8)
        
        # Get status info
        is_detecting = status_data.get('is_detecting', False) if status_data else False
        persons = status_data.get('stream_status', {}).get('persons', []) if status_data else []
        
        # Title
        cv2.putText(img, "ABRS - Absent Detection", (20, 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
        
        # Status section
        y_pos = 90
        
        # Detection status
        if is_detecting:
            cv2.putText(img, "Status: RUNNING", (20, y_pos), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        else:
            cv2.putText(img, "Status: STOPPED", (20, y_pos), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        
        y_pos += 50
        
        # Person status
        if persons:
            person = persons[0]
            person_status = person.get('status', 'Unknown')
            absent_duration = person.get('absent_duration', 0)
            person_id = person.get('person_id', 'Unknown')
            
            cv2.putText(img, f"Person ID: {person_id}", (20, y_pos), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            y_pos += 40
            
            if person_status == "在岗":
                status_color = (0, 255, 0)
                status_text = "PRESENT"
            elif person_status == "离岗":
                status_color = (0, 0, 255)
                status_text = "ABSENT"
            else:
                status_color = (255, 255, 0)
                status_text = "UNKNOWN"
            
            cv2.putText(img, f"Status: {status_text}", (20, y_pos), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)
            y_pos += 40
            
            if absent_duration > 0:
                cv2.putText(img, f"Absent Time: {absent_duration:.1f}s", (20, y_pos), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                y_pos += 40
        else:
            cv2.putText(img, "Status: NO PERSON DETECTED", (20, y_pos), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            y_pos += 80
        
        # Alarm section
        y_pos += 20
        cv2.line(img, (20, y_pos), (580, y_pos), (128, 128, 128), 2)
        y_pos += 40
        
        cv2.putText(img, "Recent Alarms:", (20, y_pos), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        y_pos += 35
        
        if alarms:
            # Show last 3 alarms
            for alarm in alarms[-3:]:
                alarm_type = alarm.get('alarm_type', '')
                alarm_time = alarm.get('alarm_time', '')
                text = f"[{alarm_time}] {alarm_type}"
                cv2.putText(img, text[:50], (20, y_pos), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                y_pos += 25
        else:
            cv2.putText(img, "No alarms", (20, y_pos), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (128, 128, 128), 1)
        
        # Hint
        cv2.putText(img, f"Threshold: {ABSENT_THRESHOLD_SEC}s | Press 'q' to exit", (20, 380), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        
        return img
    
    def show_live_status(self):
        """Show live status display (no camera - backend is using it)"""
        print("\n" + "=" * 60)
        print("[Live] Real-time detection started...")
        print("=" * 60)
        print("Hints:")
        print(f"  - Face camera: marked as 'PRESENT'")
        print(f"  - Leave camera: triggers 'ABSENT ALARM' after {ABSENT_THRESHOLD_SEC}s")
        print(f"  - Return to camera: marked as 'BACK'")
        print("\nPress 'q' to exit")
        print("=" * 60)
        
        last_alarm_count = 0
        last_status_time = 0
        status_cache = None
        alarms_cache = []
        
        while self.is_running:
            # Update status every 0.5 seconds
            current_time = time.time()
            if current_time - last_status_time > 0.5:
                status_cache = self.get_status()
                alarms_cache = self.get_alarms()
                last_status_time = current_time
                
                # Print status to console
                if status_cache:
                    persons = status_cache.get('stream_status', {}).get('persons', [])
                    if persons:
                        person = persons[0]
                        status = person.get('status', 'Unknown')
                        duration = person.get('absent_duration', 0)
                        print(f"\r[Status] {status} | Absent: {duration:.1f}s | Alarms: {len(alarms_cache)}", end='', flush=True)
            
            # Print new alarms to console
            if len(alarms_cache) > last_alarm_count:
                new_alarms = alarms_cache[last_alarm_count:]
                for alarm in new_alarms:
                    print(f"\n[ALARM] [{alarm.get('alarm_type')}] {alarm.get('alarm_time')}")
                last_alarm_count = len(alarms_cache)
            
            # Create and show status image
            status_img = self.create_status_image(status_cache, alarms_cache)
            cv2.imshow("ABRS - Detection Status (Press 'q' to exit)", status_img)
            
            # Check key press
            key = cv2.waitKey(100) & 0xFF  # 100ms delay for ~10fps
            if key == ord('q'):
                print("\n[Warning] User requested to exit")
                break
        
        cv2.destroyAllWindows()
    
    def stop_detection(self):
        """Stop detection"""
        print("\n[Detection] Stopping detection...")
        self.is_running = False
        
        try:
            response = requests.post(f"{BASE_URL}/absent/stop", timeout=2)
            if response.status_code == 200:
                print("[OK] Detection stopped")
        except:
            pass
    
    def show_final_report(self):
        """Show final report"""
        print("\n" + "=" * 60)
        print("[Report] Demo Report")
        print("=" * 60)
        
        alarms = self.get_alarms()
        if alarms:
            print(f"\nTotal {len(alarms)} alarms generated:")
            for i, alarm in enumerate(alarms[-10:], 1):
                print(f"  {i}. [{alarm.get('alarm_type')}] {alarm.get('alarm_time')}")
        else:
            print("\nNo alarms generated")
        
        print("=" * 60)
    
    def cleanup(self):
        """Cleanup demo data"""
        print("\n[Cleanup] Cleaning up demo data...")
        
        # Stop detection
        if self.is_running:
            self.stop_detection()
        
        # Delete person
        try:
            requests.post(f"{BASE_URL}/absent/person/delete", 
                         params={"person_id": "DEMO_PERSON_001"}, timeout=2)
            print("[OK] Demo person deleted")
        except:
            pass
        
        # Delete video source
        try:
            requests.post(f"{BASE_URL}/source/delete", 
                         params={"source_id": "DEMO_CAMERA_001"}, timeout=2)
            print("[OK] Demo video source deleted")
        except:
            pass
        
        # Release camera if still open
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()
    
    def run(self):
        """Run complete demo"""
        print("=" * 60)
        print("Absent Detection Module - Local Camera Demo")
        print("=" * 60)
        
        try:
            # Step 1: Capture face image
            face_img = self.capture_face()
            if face_img is None:
                print("[Error] Demo aborted: cannot get face image")
                return
            
            # Step 2: Add demo person
            if not self.add_demo_person(face_img):
                print("[Error] Demo aborted: failed to add person")
                return
            
            # Step 3: Add camera source
            self.add_camera_source()
            
            # Step 4: Start detection
            if not self.start_detection():
                print("[Error] Demo aborted: failed to start detection")
                self.cleanup()
                return
            
            # Step 5: Show live status (backend is using camera)
            self.show_live_status()
            
            # Step 6: Show final report
            self.show_final_report()
            
        except KeyboardInterrupt:
            print("\n\nUser interrupted demo")
        except Exception as e:
            print(f"\n[Error] Demo error: {e}")
        finally:
            # Cleanup
            self.cleanup()
            print("\n[OK] Demo completed")
            print("=" * 60)


def main():
    """Main function"""
    # Check if service is running
    try:
        response = requests.get("http://localhost:8000/health", timeout=2)
        if response.status_code != 200:
            print("[Error] Service not running, please start: python run.py")
            sys.exit(1)
    except:
        print("[Error] Cannot connect to service, please start: python run.py")
        sys.exit(1)
    
    # Run demo
    demo = CameraDemo()
    demo.run()


if __name__ == "__main__":
    main()
