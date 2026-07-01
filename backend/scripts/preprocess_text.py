import re
import glob
import os

# 1. 스크립트 위치 기반으로 절대 경로 계산
current_dir = os.path.dirname(os.path.abspath(__file__))
target_folder = os.path.join(current_dir, '..', 'data', 'standard_contracts')
target_pattern = os.path.join(target_folder, '**', '*.txt')

# 조건에 맞는 모든 txt 파일 경로 가져오기
file_list = glob.glob(target_pattern, recursive=True)

if not file_list:
    print(f"경로에서 txt 파일을 찾을 수 없습니다: {target_folder}")
else:
    for file_path in file_list:
        # 2. 파일 읽기
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # 3. [1단계] 제어 문자 일괄 제거 (BEL, FF 등)
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', content)

        # 4. [2단계] '<그림>', '<표>' 문자열 제거
        cleaned = cleaned.replace('<그림>', '')
        cleaned = cleaned.replace('<표>', '')

        # 5. [3단계] 불규칙한 특수문자 불렛을 마크다운 표준(-)으로 정규화
        # 줄의 시작(^)에 위치한 ◇, ※, *, □, ○ 기호와 뒤따르는 공백을 '- '로 치환
        cleaned = re.sub(r'^[◇※\*□○]\s*', '- ', cleaned, flags=re.MULTILINE)
        
        # 한글 자음 'ㅇ'이 불렛으로 쓰인 경우 치환 (뒤에 반드시 공백이 1개 이상 있는 경우만)
        cleaned = re.sub(r'^ㅇ\s+', '- ', cleaned, flags=re.MULTILINE)

        # 6. [4단계] 연속된 빈 줄(공백 라인) 축소
        cleaned = re.sub(r'\n\s*\n', '\n\n', cleaned)

        # 7. 원래 파일에 수정본 덮어쓰기 저장
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(cleaned)

        # 파일명만 출력
        file_name = os.path.basename(file_path)
        print(f"✔️ 정제 완료: {file_name}")

    print(f"\n🚀 총 {len(file_list)}개 파일 전처리 완료")