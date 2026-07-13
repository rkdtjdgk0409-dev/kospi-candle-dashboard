# 코스피·코스닥 캔들 차트 자동 갱신

## 교체할 파일
저장소 루트에 다음 파일을 업로드합니다.

- `index.html`
- `update.py`
- `requirements.txt`
- `.github/workflows/update.yml`

기존 파일이 있으면 같은 이름으로 덮어씁니다.

## 최초 설정
1. GitHub 저장소 `Settings → Pages`
2. `Build and deployment → Source`를 **GitHub Actions**로 선택
3. `Actions → 코스피 코스닥 차트 자동 갱신 → Run workflow`
4. 실행 완료 후 Pages 주소를 노션 `/embed`에 붙여넣기

## 자동 실행
평일 매시 07분과 37분에 실행합니다. GitHub Actions 스케줄은 수 분 지연될 수 있습니다.

## 자동 갱신 확인
페이지 맨 아래 `마지막 자동 갱신` 시간이 바뀌는지 확인합니다.
브라우저/노션 캐시 방지를 위해 `data.json?v=현재시간` 방식으로 읽습니다.
