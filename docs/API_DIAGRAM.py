#!/usr/bin/env python3
"""
API Design Visualizer for Audio Looper System
Creates interactive diagrams showing component relationships and API calls
Uses only matplotlib - no external dependencies needed
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, ConnectionPatch
import math

class APIDesignVisualizer:
    def __init__(self):
        self.components = {
            'AudioManager': {
                'position': (2, 3),
                'color': '#FF6B6B',
                'methods': [
                    'start_all_sounds()',
                    'stop_all_sounds()',
                    'fade_in(instrument, duration)',
                    'fade_out(instrument, duration)',
                    'fade_instrument(instrument, target_vol, duration)',
                    'get_volume(instrument)',
                    'is_fading(instrument)',
                    'get_available_instruments()'
                ]
            },
            'SyncController': {
                'position': (2, 2),
                'color': '#4ECDC4',
                'methods': [
                    'handle_input(input_data)',
                    'start()',
                    'shutdown()',
                    '_activate_instrument(instrument)',
                    '_stop_all()',
                    '_show_status()',
                    '_update_timers()'
                ]
            },
            'ButtonHandler': {
                'position': (1, 2),
                'color': '#45B7D1',
                'methods': [
                    'start()',
                    'stop()',
                    '_process_key(key)',
                    '_gpio_loop()',
                    '_windows_loop()',
                    '_unix_loop()'
                ]
            },
            'PlatformDetector': {
                'position': (1, 1),
                'color': '#96CEB4',
                'methods': [
                    'detect_platform(force_platform)',
                    'get_available_input_methods(platform)',
                    'get_best_input_method(platform, config)',
                    'check_gpio_available()'
                ]
            },
            'Main Application': {
                'position': (2, 1),
                'color': '#FFEAA7',
                'methods': [
                    'run()',
                    'shutdown()',
                    '_check_requirements()'
                ]
            }
        }
        
        self.api_calls = [
            # From Main to components
            ('Main Application', 'AudioManager', 'AudioManager()'),
            ('Main Application', 'SyncController', 'SyncController(config, audio_manager)'),
            ('Main Application', 'ButtonHandler', 'ButtonHandler(callback)'),
            
            # From ButtonHandler to SyncController
            ('ButtonHandler', 'SyncController', 'handle_input(1-8)'),
            ('ButtonHandler', 'SyncController', 'handle_input("status")'),
            ('ButtonHandler', 'SyncController', 'handle_input("stop")'),
            
            # From SyncController to AudioManager
            ('SyncController', 'AudioManager', 'start_all_sounds()'),
            ('SyncController', 'AudioManager', 'stop_all_sounds()'),
            ('SyncController', 'AudioManager', 'fade_in(instrument, duration)'),
            ('SyncController', 'AudioManager', 'fade_out(instrument, duration)'),
            ('SyncController', 'AudioManager', 'get_volume(instrument)'),
            ('SyncController', 'AudioManager', 'is_fading(instrument)'),
            
            # From ButtonHandler to PlatformDetector
            ('ButtonHandler', 'PlatformDetector', 'detect_platform()'),
            ('ButtonHandler', 'PlatformDetector', 'get_best_input_method()')
        ]

    def create_component_diagram(self):
        """Create a component relationship diagram"""
        fig, ax = plt.subplots(1, 1, figsize=(14, 10))
        ax.set_xlim(0, 4)
        ax.set_ylim(0, 4)
        ax.set_aspect('equal')
        
        # Draw components
        boxes = {}
        for name, info in self.components.items():
            x, y = info['position']
            
            # Create fancy box
            box = FancyBboxPatch(
                (x-0.4, y-0.3), 0.8, 0.6,
                boxstyle="round,pad=0.02",
                facecolor=info['color'],
                edgecolor='black',
                linewidth=2,
                alpha=0.8
            )
            ax.add_patch(box)
            boxes[name] = (x, y)
            
            # Add component name
            ax.text(x, y, name, ha='center', va='center', 
                   fontsize=10, fontweight='bold', wrap=True)
        
        # Draw connections
        for source, target, method in self.api_calls:
            if source in boxes and target in boxes:
                x1, y1 = boxes[source]
                x2, y2 = boxes[target]
                
                # Draw arrow
                arrow = ConnectionPatch((x1, y1), (x2, y2), "data", "data",
                                      arrowstyle="->", shrinkA=40, shrinkB=40,
                                      mutation_scale=20, fc="black", alpha=0.6)
                ax.add_patch(arrow)
        
        ax.set_title('Audio Looper System - Component Architecture', 
                    fontsize=16, fontweight='bold', pad=20)
        ax.axis('off')
        
        # Add legend
        legend_text = """
        Component Interactions:
        • Main Application orchestrates all components
        • ButtonHandler captures input and sends to SyncController
        • SyncController manages timing and calls AudioManager
        • PlatformDetector provides platform-specific configuration
        • AudioManager handles all audio playback and effects
        """
        ax.text(0.1, 0.2, legend_text, fontsize=9, va='top', 
               bbox=dict(boxstyle="round,pad=0.5", facecolor='lightgray', alpha=0.8))
        
        plt.tight_layout()
        return fig

    def create_api_flow_diagram(self):
        """Create detailed API flow diagram"""
        fig, ax = plt.subplots(1, 1, figsize=(16, 12))
        
        # Define flow steps
        flow_steps = [
            ("User Input", "Key Press (1-8) or GPIO Button", '#FF9999'),
            ("ButtonHandler", "_process_key() → callback(instrument_id)", '#99CCFF'),
            ("SyncController", "handle_input(instrument_id)", '#99FF99'),
            ("Audio Check", "if not self.active: audio_manager.start_all_sounds()", '#FFCC99'),
            ("Fade In", "audio_manager.fade_in(instrument, duration)", '#CC99FF'),
            ("Timer Reset", "instrument_timers[i] = timeout\nglobal_timer = timeout", '#99FFCC'),
            ("Background Loop", "_timer_loop() → _update_timers()", '#FFB366'),
            ("Timeout Check", "if timer <= 0: fade_out(instrument)", '#FF99CC')
        ]
        
        # Draw flow diagram
        y_positions = [0.9 - i * 0.1 for i in range(len(flow_steps))]
        
        for i, (title, description, color) in enumerate(flow_steps):
            y = y_positions[i]
            
            # Draw box
            rect = FancyBboxPatch(
                (0.1, y-0.04), 0.8, 0.08,
                boxstyle="round,pad=0.01",
                facecolor=color,
                edgecolor='black',
                alpha=0.8
            )
            ax.add_patch(rect)
            
            # Add text
            ax.text(0.15, y, f"{i+1}. {title}", fontweight='bold', fontsize=11, va='center')
            ax.text(0.15, y-0.02, description, fontsize=9, va='center')
            
            # Draw arrow to next step
            if i < len(flow_steps) - 1:
                arrow = patches.FancyArrowPatch(
                    (0.5, y-0.04), (0.5, y_positions[i+1]+0.04),
                    arrowstyle='->', mutation_scale=20, 
                    color='black', alpha=0.7
                )
                ax.add_patch(arrow)
        
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_title('Audio Looper System - API Call Flow', 
                    fontsize=16, fontweight='bold', pad=20)
        ax.axis('off')
        
        plt.tight_layout()
        return fig

    def create_method_details_diagram(self):
        """Create detailed method signature diagram"""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        
        # AudioManager methods
        self._draw_method_box(ax1, 'AudioManager', self.components['AudioManager']['methods'],
                             self.components['AudioManager']['color'])
        
        # SyncController methods  
        self._draw_method_box(ax2, 'SyncController', self.components['SyncController']['methods'],
                             self.components['SyncController']['color'])
        
        # ButtonHandler methods
        self._draw_method_box(ax3, 'ButtonHandler', self.components['ButtonHandler']['methods'],
                             self.components['ButtonHandler']['color'])
        
        # PlatformDetector methods
        self._draw_method_box(ax4, 'PlatformDetector', self.components['PlatformDetector']['methods'],
                             self.components['PlatformDetector']['color'])
        
        fig.suptitle('Audio Looper System - API Method Details', 
                    fontsize=16, fontweight='bold')
        plt.tight_layout()
        return fig

    def _draw_method_box(self, ax, component_name, methods, color):
        """Helper to draw method details in a box"""
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        
        # Title
        ax.text(0.5, 0.95, component_name, ha='center', va='top', 
               fontsize=14, fontweight='bold')
        
        # Background box
        rect = FancyBboxPatch(
            (0.05, 0.05), 0.9, 0.85,
            boxstyle="round,pad=0.02",
            facecolor=color,
            alpha=0.3,
            edgecolor='black'
        )
        ax.add_patch(rect)
        
        # Methods
        y_start = 0.85
        for i, method in enumerate(methods):
            y_pos = y_start - (i * 0.08)
            if y_pos > 0.1:  # Don't go below bottom
                ax.text(0.1, y_pos, f"• {method}", fontsize=9, va='top', 
                       fontfamily='monospace')
        
        ax.axis('off')

    def create_data_flow_diagram(self):
        """Create clean data flow diagram as a table/matrix"""
        fig, ax = plt.subplots(1, 1, figsize=(16, 10))
        
        # Create data flow table
        data_flows = [
            # From, To, Data Type, Description
            ('Main Application', 'AudioManager', 'config: dict', 'Configuration parameters'),
            ('Main Application', 'SyncController', 'config + audio_manager', 'Config dict and AudioManager instance'),
            ('Main Application', 'ButtonHandler', 'callback: function', 'Function pointer to handle_input()'),
            ('ButtonHandler', 'SyncController', 'input_data: int|str', 'Instrument numbers (1-8) or commands'),
            ('SyncController', 'AudioManager', 'instrument_id: int', 'Which instrument to control (1-8)'),
            ('SyncController', 'AudioManager', 'volume: float', 'Target volume (0.0 - 1.0)'),
            ('SyncController', 'AudioManager', 'duration: float', 'Fade duration in seconds'),
            ('AudioManager', 'SyncController', 'status: bool', 'Success/failure of operations'),
            ('AudioManager', 'SyncController', 'volume: float', 'Current volume levels'),
            ('AudioManager', 'SyncController', 'is_fading: bool', 'Whether instrument is fading'),
            ('PlatformDetector', 'ButtonHandler', 'platform: str', 'Platform type (windows/linux/raspberry_pi)'),
            ('PlatformDetector', 'ButtonHandler', 'input_method: str', 'Best input method for platform')
        ]
        
        # Define colors for each component
        component_colors = {
            'Main Application': '#FFEAA7',
            'AudioManager': '#FF6B6B', 
            'SyncController': '#4ECDC4',
            'ButtonHandler': '#45B7D1',
            'PlatformDetector': '#96CEB4'
        }
        
        # Create table layout
        ax.set_xlim(0, 10)
        ax.set_ylim(0, len(data_flows) + 2)
        
        # Table headers
        headers = ['From Component', 'To Component', 'Data Type', 'Description']
        header_positions = [1, 3, 5, 7.5]
        
        for i, header in enumerate(headers):
            ax.text(header_positions[i], len(data_flows) + 1, header, 
                   fontsize=12, fontweight='bold', ha='left', va='center',
                   bbox=dict(boxstyle="round,pad=0.3", facecolor='lightgray', alpha=0.8))
        
        # Draw data flow rows
        for row_idx, (from_comp, to_comp, data_type, description) in enumerate(data_flows):
            y_pos = len(data_flows) - row_idx
            
            # From component (colored)
            ax.text(1, y_pos, from_comp, fontsize=10, ha='left', va='center',
                   bbox=dict(boxstyle="round,pad=0.2", 
                            facecolor=component_colors.get(from_comp, 'white'), alpha=0.6))
            
            # Arrow
            ax.text(2.5, y_pos, '→', fontsize=16, ha='center', va='center', fontweight='bold')
            
            # To component (colored)
            ax.text(3, y_pos, to_comp, fontsize=10, ha='left', va='center',
                   bbox=dict(boxstyle="round,pad=0.2",
                            facecolor=component_colors.get(to_comp, 'white'), alpha=0.6))
            
            # Data type
            ax.text(5, y_pos, data_type, fontsize=10, ha='left', va='center',
                   fontfamily='monospace',
                   bbox=dict(boxstyle="round,pad=0.2", facecolor='lightyellow', alpha=0.8))
            
            # Description
            ax.text(7.5, y_pos, description, fontsize=9, ha='left', va='center')
            
            # Subtle row separator
            if row_idx % 2 == 0:
                rect = plt.Rectangle((0.5, y_pos-0.3), 9, 0.6, 
                                   facecolor='lightblue', alpha=0.1)
                ax.add_patch(rect)
        
        ax.set_title('Audio Looper System - Data Flow Matrix', 
                    fontsize=16, fontweight='bold', pad=20)
        ax.axis('off')
        
        # Add summary box
        summary_text = """
        KEY DATA PATTERNS:
        • Configuration flows down from Main to all components
        • User input flows: ButtonHandler → SyncController → AudioManager  
        • Status/feedback flows back: AudioManager → SyncController
        • Platform detection provides setup info to ButtonHandler
        • All data is strongly typed (int, float, bool, str, dict)
        """
        ax.text(0.5, 0.5, summary_text, fontsize=10, va='top',
               bbox=dict(boxstyle="round,pad=0.5", facecolor='lightgreen', alpha=0.8))
        
        plt.tight_layout()
        return fig

    def generate_all_diagrams(self):
        """Generate all API design diagrams"""
        print("Generating API Design Diagrams...")
        
        # Create all diagrams
        fig1 = self.create_component_diagram()
        fig2 = self.create_api_flow_diagram()
        fig3 = self.create_method_details_diagram()
        fig4 = self.create_data_flow_diagram()
        
        # Save diagrams
        fig1.savefig('api_component_architecture.png', dpi=300, bbox_inches='tight')
        fig2.savefig('api_call_flow.png', dpi=300, bbox_inches='tight')
        fig3.savefig('api_method_details.png', dpi=300, bbox_inches='tight')
        fig4.savefig('api_data_flow.png', dpi=300, bbox_inches='tight')
        
        print("✅ Generated diagrams:")
        print("  - api_component_architecture.png")
        print("  - api_call_flow.png") 
        print("  - api_method_details.png")
        print("  - api_data_flow.png")
        
        # Show all diagrams
        plt.show()

def main():
    """Main function to generate API design visualization"""
    try:
        visualizer = APIDesignVisualizer()
        visualizer.generate_all_diagrams()
        
        print("\n" + "="*50)
        print("API DESIGN ANALYSIS COMPLETE")
        print("="*50)
        print("\nKey API Design Insights:")
        print("• Clean separation of concerns")
        print("• Callback-based communication pattern")
        print("• Threaded architecture with proper synchronization")
        print("• Platform abstraction through PlatformDetector")
        print("• Audio effects handled asynchronously")
        print("• Configuration-driven design")
        
    except ImportError as e:
        print(f"Missing required library: {e}")
        print("Install matplotlib with: python -m pip install matplotlib")
        print("Or try: py -m pip install matplotlib")
    except Exception as e:
        print(f"Error generating diagrams: {e}")

if __name__ == "__main__":
    main()