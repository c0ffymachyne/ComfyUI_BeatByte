import torch
import numpy as np
import ast
from typing import Tuple, Dict

class BytebeatSynth:
    @classmethod
    def INPUT_TYPES(cls) -> Dict:

        # (t * (t >> 5 & 7 | t >> 10) & 63) + (t >> 7 & 127)
        # (t * (t >> 9 | t >> 13) & 16) & 255
        return {
            "required": {
                "samplerate": ("INT", {"default": 8000, "min": 8000, "max": 96000, "step": 1}),
                "duration": ("FLOAT", {"default": 15.0, "min": 1.0, "max": 60.0, "step": 0.1}),
                "expression": ("STRING", {"default": "(t * (t >> 9 | t >> 13) & 16) & 255", "multiline": False, "hint": "Provide a C-like expression using t, bitwise operators, and arithmetic."})
            }
        }

    RETURN_TYPES = ("AUDIO", "INT")
    RETURN_NAMES = ("audio", "sample_rate")
    CATEGORY = "Synthesizer"
    FUNCTION = "process"

    def process(
        self,
        samplerate: int,
        duration: float,
        expression: str,
    ) -> Tuple[Dict[str, torch.Tensor]]:
        """
        Generates audio using the Bytebeat synthesis method.

        Parameters:
            samplerate (int): Sampling rate in Hz.
            duration (float): Duration of the audio in seconds.
            expression (str): Bytebeat expression as a C-like string.

        Returns:
            Tuple[Dict[str, torch.Tensor]]: Generated audio waveform and sample rate.
        """

        # Validate inputs
        if samplerate < 8000 or samplerate > 96000:
            raise ValueError("Sample rate must be between 8000 and 96000 Hz.")
        if duration < 1.0 or duration > 60.0:
            raise ValueError("Duration must be between 1.0 and 60.0 seconds.")

        # Calculate total number of samples
        total_samples = int(samplerate * duration)

        # Create an array of time indices
        t = np.arange(total_samples, dtype=np.uint32)

        # Safely evaluate the Bytebeat expression
        try:
            samples = self.safe_eval_expression(expression, t)
        except Exception as e:
            raise ValueError(f"Error evaluating expression: {e}")

        # Ensure samples are in 8-bit range [0, 255]
        samples = samples.astype(np.int16)
        samples = (samples - 128) * 256  # Normalize to 16-bit range

        # Convert to PyTorch tensor
        waveform = torch.from_numpy(samples).float()

        # Normalize waveform to prevent clipping
        max_val = torch.max(torch.abs(waveform))
        if max_val > 0:
            waveform = waveform / max_val * 0.9  # Scale to 90% to prevent clipping

        # Add channel dimension (mono)
        waveform = waveform.unsqueeze(0)  # Shape: [1, samples]

        # Add batch dimension if required by the framework
        waveform = waveform.unsqueeze(0)  # Shape: [1, 1, samples]

        # Prepare the return dictionary
        return {"waveform": waveform, "sample_rate": samplerate}, samplerate

    def safe_eval_expression(self, expr: str, t: np.ndarray) -> np.ndarray:
        """
        Safely evaluate a Bytebeat expression.

        Parameters:
            expr (str): Bytebeat expression as a string.
            t (np.ndarray): Array of time indices.

        Returns:
            np.ndarray: Evaluated audio samples.
        """

        # Define allowed names and functions
        allowed_names = {
            't': t,
            'np': np,
            'sin': np.sin,
            'cos': np.cos,
            'tan': np.tan,
            'exp': np.exp,
            'sqrt': np.sqrt,
            'log': np.log,
            'abs': np.abs,
            'min': np.minimum,
            'max': np.maximum,
            # Add more numpy functions if needed
        }

        # Parse the expression to ensure it's safe
        try:
            node = ast.parse(expr, mode='eval')
        except SyntaxError as e:
            raise ValueError(f"Syntax error in expression: {e}")

        # Recursively validate the AST nodes
        for subnode in ast.walk(node):
            if isinstance(subnode, ast.Call):
                if not isinstance(subnode.func, ast.Name) or subnode.func.id not in allowed_names:
                    raise ValueError(f"Function '{subnode.func.id}' is not allowed.")
            elif isinstance(subnode, ast.Name):
                if subnode.id not in allowed_names:
                    raise ValueError(f"Use of name '{subnode.id}' is not allowed.")
            elif isinstance(subnode, (ast.BinOp, ast.UnaryOp, ast.Num, ast.Expression,
                                      ast.Load, ast.Add, ast.Sub, ast.Mult, ast.Div,
                                      ast.Mod, ast.Pow, ast.BitOr, ast.BitAnd, ast.BitXor,
                                      ast.RShift, ast.LShift, ast.USub, ast.UAdd)):
                continue
            else:
                raise ValueError(f"Unsupported expression element: {type(subnode).__name__}")

        # Compile and evaluate the expression
        try:
            compiled_expr = compile(node, '<string>', 'eval')
            result = eval(compiled_expr, {"__builtins__": None}, allowed_names)
        except Exception as e:
            raise ValueError(f"Error during evaluation: {e}")

        if not isinstance(result, np.ndarray):
            raise ValueError("The expression must return a NumPy array.")

        return result


NODE_CLASS_MAPPINGS = {
    "BytebeatSynth":BytebeatSynth
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BytebeatSynth": "ByteBeat Synth" 
}

