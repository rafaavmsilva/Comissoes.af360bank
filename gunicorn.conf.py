import os

workers = 1
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
timeout = 120
accesslog = '-'
errorlog = '-'
