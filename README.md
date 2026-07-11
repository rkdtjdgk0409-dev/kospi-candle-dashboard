# 코스피 캔들 차트

컴퓨터에 Python을 설치하지 않아도 됩니다.

GitHub Actions가 평일 장 마감 후 네이버 증권의 공개 코스피 일봉 데이터를
가져와 data.json을 갱신하고, GitHub Pages가 캔들 차트를 표시합니다.

## 설치 순서

1. GitHub에서 `kospi-candle-dashboard`라는 Public 저장소를 만듭니다.
2. 이 압축파일을 풀고 안에 있는 파일 전체를 저장소에 업로드합니다.
3. Actions에서 `코스피 캔들 데이터 자동 갱신`을 수동 실행합니다.
4. 초록색 체크가 나오면 Settings → Pages로 이동합니다.
5. `Deploy from a branch`, `main`, `/ (root)`를 선택합니다.
6. 생성된 주소를 노션의 `/embed` 블록에 넣습니다.

예상 주소:

https://rkdtjdgk0409-dev.github.io/kospi-candle-dashboard/

## 자동 실행

평일 한국시간 오후 4시 35분에 실행되도록 설정되어 있습니다.
GitHub 서버 상황에 따라 실행이 다소 늦을 수 있습니다.

## 주의

네이버가 공개 웹 응답 구조를 바꾸면 자동 수집 코드 수정이 필요할 수 있습니다.
데이터는 실시간 주문 또는 투자 판단용이 아니라 개인 참고용으로 사용하세요.
