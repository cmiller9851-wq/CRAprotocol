from .logger import record_event

def run_inference(model, inputs):
    record_event("inference_start", {"model_path": model.path, "inputs": inputs})
    outputs = model.predict(inputs)
    record_event("inference_end", {"model_path": model.path, "outputs": outputs})
    return outputs
