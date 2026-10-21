"""
Video recording utilities for TAMP evaluation.
Based on omnigibson/eval/evaluator.py
"""

import numpy as np
import cv2
from omnigibson.eval.utils.obs_utils import create_video_writer, write_video


def log(msg):
    """Log message"""
    import sys
    print(msg, file=sys.stderr, flush=True)
    print(msg, flush=True)


class VideoRecorder:
    """Video recorder for R1Pro robot with 3-camera layout"""

    def __init__(self):
        self.video_writer = None
        self.video_path = None
        self.video_rate = 30
        self.obs = None  # Preprocessed observations

    def start_recording(self, fpath, rate=30):
        """Arm video recording (writer created lazily on first frame)"""
        self.stop_recording()  # Close any existing writer
        self.video_path = fpath
        self.video_rate = rate
        log(f"[VideoRecorder] Recording armed: {fpath}")

    def stop_recording(self):
        """Finalize and close video writer"""
        if self.video_writer is not None:
            try:
                container, stream = self.video_writer
                # Flush remaining packets
                for packet in stream.encode():
                    container.mux(packet)
                container.close()
                log(f"[VideoRecorder] Video saved: {self.video_path}")
            except Exception as e:
                log(f"[VideoRecorder] Video finalization failed: {e}")

        self.video_writer = None
        self.video_path = None

    def preprocess_obs(self, obs, robot_name):
        """Flatten observation structure for easier access

        Converts obs[robot_name][sensor_name][modality]
        to obs_flat[robot_name:sensor_name::modality]
        """
        if obs is None:
            return None

        flat_obs = {}

        # Flatten robot observations
        if robot_name in obs:
            robot_obs = obs[robot_name]
            for sensor_name, sensor_data in robot_obs.items():
                if isinstance(sensor_data, dict):
                    for modality, data in sensor_data.items():
                        key = f"{robot_name}:{sensor_name}::{modality}"
                        flat_obs[key] = data
                else:
                    flat_obs[sensor_name] = sensor_data

        # Keep task obs
        if 'task' in obs:
            flat_obs['task'] = obs['task']

        return flat_obs

    def write_frame(self, obs, robot_name):
        """Write one video frame using R1Pro's 3 cameras

        Layout:
            [left_wrist  (224x224)] [head (448x448)]
            [right_wrist (224x224)]

        Args:
            obs: Raw observation from env.get_obs()
            robot_name: Name of the robot (e.g., "robot0")
        """
        if self.video_path is None:
            return

        try:
            # Preprocess observations
            self.obs = self.preprocess_obs(obs, robot_name)

            if self.obs is None:
                return

            # Camera sensor names for R1Pro
            left_wrist_key = f"{robot_name}:left_realsense_link:Camera:0::rgb"
            right_wrist_key = f"{robot_name}:right_realsense_link:Camera:0::rgb"
            head_key = f"{robot_name}:zed_link:Camera:0::rgb"

            # Check if all cameras are available
            if not all(key in self.obs for key in [left_wrist_key, right_wrist_key, head_key]):
                log(f"[VideoRecorder] Warning: Missing camera views")
                return

            # Get RGB from each camera and resize
            # Note: Observations are torch tensors, need to convert to numpy
            left_wrist_rgb = cv2.resize(
                self.obs[left_wrist_key].cpu().numpy() if hasattr(self.obs[left_wrist_key], 'cpu') else self.obs[left_wrist_key],
                (224, 224),
            )
            right_wrist_rgb = cv2.resize(
                self.obs[right_wrist_key].cpu().numpy() if hasattr(self.obs[right_wrist_key], 'cpu') else self.obs[right_wrist_key],
                (224, 224),
            )
            head_rgb = cv2.resize(
                self.obs[head_key].cpu().numpy() if hasattr(self.obs[head_key], 'cpu') else self.obs[head_key],
                (448, 448),
            )

            # Remove alpha channel if present (RGBA -> RGB)
            if left_wrist_rgb.shape[-1] == 4:
                left_wrist_rgb = left_wrist_rgb[..., :3]
            if right_wrist_rgb.shape[-1] == 4:
                right_wrist_rgb = right_wrist_rgb[..., :3]
            if head_rgb.shape[-1] == 4:
                head_rgb = head_rgb[..., :3]

            # Composite frame: stack wrist cams vertically, concatenate with head
            # Result: 448x672x3
            frame = np.expand_dims(
                np.hstack([
                    np.vstack([left_wrist_rgb, right_wrist_rgb]),
                    head_rgb
                ]),
                0  # Add batch dimension for write_video
            )

            # Create writer lazily on first frame
            if self.video_writer is None:
                log(f"[VideoRecorder] Creating writer: resolution={frame.shape[1:3]}")
                self.video_writer = create_video_writer(
                    self.video_path,
                    resolution=frame.shape[1:3],  # (H, W)
                    rate=self.video_rate
                )

            # Write frame immediately
            write_video(frame, video_writer=self.video_writer, batch_size=1, mode="rgb")

        except Exception as e:
            log(f"[VideoRecorder] Frame write failed: {e}")
            import traceback
            log(traceback.format_exc())
