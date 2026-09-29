import os
import sys

# 프로젝트 루트 경로를 sys.path에 추가하여 app.py 모듈 임포트 가능하도록 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from app import app
