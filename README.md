# 코스피 캔들 차트 수정 파일

기존 `kospi-candle-dashboard` 저장소에서 다음 파일을 같은 경로에 덮어씁니다.

- `index.html`
- `.github/workflows/update.yml`

코스피 차트가 나오지 않던 원인은 `data.json`의 `market` 구조와 화면 파일이 찾던 `markets.kospi` 구조가 서로 달랐기 때문입니다. 새 `index.html`은 코스피 전용 `market` 구조를 사용합니다.

자동 갱신은 평일 한국시간 오후 4시(UTC 07:00), 장 마감 후 종가 기준입니다. 노션 임베드 주소는 그대로 사용합니다.

https://rkdtjdgk0409-dev.github.io/kospi-candle-dashboard/
