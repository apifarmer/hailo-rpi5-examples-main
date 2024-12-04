import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import os

# Available model paths - updated to use local resources
HAILO8_MODELS = {
    'yolov5m': 'resources/yolov5m_wo_spp.hef',
    'yolov8s': 'resources/yolov8s.hef',
    'yolov8m': 'resources/yolov8m.hef',
    'yolov6n': 'resources/yolov6n.hef'
}

HAILO8L_MODELS = {
    'yolov8s': 'resources/yolov8s_h8l.hef',
    'yolov6n': 'resources/yolov6n.hef',
    'yolox_s': 'resources/yolox_s_leaky_h8l_mz.hef'
}

class GStreamerIPCameraApp:
    """
    GStreamer pipeline class for IP camera detection using Hailo acceleration
    """
    def __init__(self, callback_function, user_data, model_name='yolov5m', is_hailo8l=False):
        """
        Initialize the GStreamer pipeline for IP camera detection
        """
        self.callback_function = callback_function
        self.user_data = user_data
        
        # Get the absolute path to the resources directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        resources_dir = os.path.join(os.path.dirname(current_dir), 'resources')
        
        # Select model path based on hardware
        models = HAILO8L_MODELS if is_hailo8l else HAILO8_MODELS
        if model_name not in models:
            available_models = ', '.join(models.keys())
            raise ValueError(f"Model {model_name} not found. Available models: {available_models}")
        
        # Construct absolute path to HEF file
        self.hef_path = os.path.join(resources_dir, models[model_name])
        if not os.path.exists(self.hef_path):
            raise RuntimeError(f"HEF file not found at {self.hef_path}")
        
        # Initialize GStreamer
        Gst.init(None)
        
        # Create the pipeline
        self.pipeline = Gst.Pipeline()
        
        # Create pipeline elements
        self.create_elements()
        
        # Add probe to get the detections
        pad = self.hailofilter.get_static_pad("src")
        pad.add_probe(Gst.PadProbeType.BUFFER, self.callback_function, self.user_data)
        
        # Add error handling
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::error', self.on_error)
        bus.connect('message::eos', self.on_eos)

    def create_elements(self):
        """Create and configure all GStreamer elements"""
        # Source elements
        self.src = Gst.ElementFactory.make("souphttpsrc", "source")
        self.src.set_property("location", "http://14.160.87.118:82/cgi-bin/camera?resolution=640&quality=1&Language=0&1733285069")
        self.src.set_property("timeout", 5)
        self.src.set_property("retries", 3)
        
        # Decoding and conversion elements
        self.jpegdec = Gst.ElementFactory.make("jpegdec", "jpeg-decoder")
        self.videoconvert = Gst.ElementFactory.make("videoconvert", "converter")
        self.videoscale = Gst.ElementFactory.make("videoscale", "scaler")
        
        # Queue elements
        self.queue1 = Gst.ElementFactory.make("queue", "queue1")
        self.queue2 = Gst.ElementFactory.make("queue", "queue2")
        
        # Configure queues
        for queue in [self.queue1, self.queue2]:
            queue.set_property("max-size-buffers", 10)
            queue.set_property("max-size-time", 0)
            queue.set_property("max-size-bytes", 0)
        
        # Video format configuration
        self.caps = Gst.Caps.from_string("video/x-raw,format=RGB,width=640,height=480")
        self.capsfilter = Gst.ElementFactory.make("capsfilter", "capsfilter")
        self.capsfilter.set_property("caps", self.caps)
        
        # Hailo elements
        self.hailonet = Gst.ElementFactory.make("hailonet", "hailonet")
        if not self.hailonet:
            raise RuntimeError("Could not create hailonet element. Make sure Hailo GStreamer plugins are installed.")
            
        self.hailofilter = Gst.ElementFactory.make("hailofilter", "hailofilter")
        if not self.hailofilter:
            raise RuntimeError("Could not create hailofilter element. Make sure Hailo GStreamer plugins are installed.")
        
        # Configure Hailo properties
        self.hailonet.set_property("hef-path", self.hef_path)
        self.hailonet.set_property("batch-size", 1)
        
        # Display element
        self.sink = Gst.ElementFactory.make("autovideosink", "sink")
        self.sink.set_property("sync", False)
        
        # Verify and add elements
        self.verify_elements()
        
        # Link elements
        self.add_and_link_elements()

    def verify_elements(self):
        """Verify all elements were created successfully"""
        elements = [self.src, self.jpegdec, self.videoconvert, self.videoscale,
                   self.capsfilter, self.queue1, self.queue2,
                   self.hailonet, self.hailofilter, self.sink]
        
        for element in elements:
            if not element:
                raise RuntimeError(f"Could not create {element}")
            self.pipeline.add(element)

    def add_and_link_elements(self):
        """Add elements to pipeline and link them"""
        try:
            self.src.link(self.jpegdec)
            self.jpegdec.link(self.videoconvert)
            self.videoconvert.link(self.videoscale)
            self.videoscale.link(self.capsfilter)
            self.capsfilter.link(self.queue1)
            self.queue1.link(self.hailonet)
            self.hailonet.link(self.hailofilter)
            self.hailofilter.link(self.queue2)
            self.queue2.link(self.sink)
        except Exception as e:
            raise RuntimeError(f"Failed to link elements: {str(e)}")

    def on_error(self, bus, message):
        """Handle pipeline errors"""
        err, debug = message.parse_error()
        print(f"Pipeline error: {err.message}")
        print(f"Debug info: {debug}")
        self.cleanup()
        self.loop.quit()

    def on_eos(self, bus, message):
        """Handle end of stream"""
        print("End of stream reached")
        self.cleanup()
        self.loop.quit()

    def run(self):
        """Run the pipeline"""
        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("Unable to set the pipeline to the playing state")
        
        self.loop = GLib.MainLoop()
        try:
            self.loop.run()
        except Exception as e:
            print(f"Pipeline error: {str(e)}")
            raise
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        print("Cleaning up pipeline...")
        self.pipeline.set_state(Gst.State.NULL)
        if hasattr(self, 'loop') and self.loop.is_running():
            self.loop.quit() 