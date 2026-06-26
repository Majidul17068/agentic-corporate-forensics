import time

def call_gemini_with_retry(client, func_name: str, *args, **kwargs):
    max_retries = 4
    delay = 10
    
    for attempt in range(max_retries):
        try:
            func = client
            for part in func_name.split('.'):
                func = getattr(func, part)
                
            return func(*args, **kwargs)
        except Exception as e:
            err_msg = str(e)
            is_rate_limit = "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower()
            
            if is_rate_limit and attempt < max_retries - 1:
                print(f"\n[!] Rate Limit (429) hit. Retrying in {delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
                delay *= 2
                continue
            
            raise e
