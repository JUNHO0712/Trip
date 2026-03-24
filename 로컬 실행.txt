로컬 실행
docker-compose up --build

실행 종료
docker compose down -v

k8s 폴더
코드를 컨테이너 이미지로 만들기
이미지들을 dockerhub에 등록

trip-backend & trip-front 폴더
도커 허브에 이미지 등록할 원본 소스코드

각 Dockerfile이 있는 디렉토리에서 실행
이미지 빌드
docker build -t junho010712/trip-front:latest . 
docker build -t junho010712/trip-backend:latest . 

이미지 등록
docker push junho010712/trip- front:latest
docker push junho010712/trip-backend:latest


클러스터

네임스페이스 생성
kubectl create namespace trip-app

파드 배포
kubectl apply -f db-deployment.yaml -n trip-app
kubectl apply -f db-init-config.yaml -n trip-app
kubectl apply -f frontend-cart-deployment.yaml -n trip-app
kubectl apply -f frontend-main-deployment.yaml -n trip-app
kubectl apply -f frontend-payment-deployment.yaml -n trip-app

서비스 확인
kubectl get svc -n trip-app

에러 로그 확인 
kubectl logs -f deployment/trip-backend -n trip-app

서비스 재시작
kubectl rollout restart deployment trip-front -n trip-app
kubectl rollout restart deployment trip-payment -n trip-app
kubectl rollout restart deployment trip-cart -n trip-app
kubectl rollout restart deployment trip-backend -n trip-app
- 도커 허브에 등록했던 이미지들


1. 배포된 주요 구성 요소 (Workloads)

프론트엔드 그룹: 사용자가 브라우저로 접속하는 화면들
trip-main: 메인 상품 목록 화면입니다.
trip-cart: 장바구니 관리 화면입니다.
trip-payment: 결제 처리 화면입니다.

백엔드 (API 서버): trip-backend가 배포되어 프론트엔드의 요청을 처리하고 DB와 통신
데이터베이스 (DB): trip-db (PostgreSQL)가 배포되어 여행 상품 및 사용자 데이터를 저장


 2. 네트워크 및 설정 (Networking & Config)

trip-main-service: 30249 포트를 통해 사용자가 웹사이트에 접속
trip-backend-service: 30088 포트를 통해 프론트엔드가 백엔드 API를 호출
trip-db: 백엔드 내부에서만 접근 가능한 DB 전용 통로

설정값(ConfigMap): db-init-sql이라는 이름으로 DB가 처음 뜰 때 실행할 SQL 스크립트(init.sql)를 저장

3. 현재의 데이터 저장 방식 (Storage)

휘발성 저장: 현재는 별도의 볼륨(PV/PVC) 없이 컨테이너 내부 저장소를 사용

초기화 방식: db-init-sql을 통해 파드가 생성될 때마다 init.sql에 적힌 10개의 상품 데이터 등으로 초기화