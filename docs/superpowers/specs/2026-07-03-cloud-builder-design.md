# Cloud Project Builder — 설계 문서

> 작성: 민준 | 날짜: 2026-07-03
> 상태: 승인됨

---

## 개요

사용자가 단계별 wizard를 통해 프로젝트 요구사항을 입력하면, 클라우드 아키텍처 설명·다이어그램·Terraform 템플릿을 자동 생성해주는 웹 도구.

- **인터페이스**: 브라우저 웹 UI
- **질문 방식**: 단계별 마법사(wizard)
- **지원 클라우드**: AWS, Azure
- **출력**: 텍스트 설명 + Mermaid 다이어그램 + Terraform 템플릿 (.tf)
- **Terraform 범위**: 템플릿 파일 수준 (실제 값은 variables.tf로 위임)

---

## 디렉터리 구조

```
cloud-builder/
├── main.py              # FastAPI 앱 진입점
├── wizard/
│   ├── steps.py         # wizard 단계 정의 (질문 목록, 순서)
│   └── state.py         # 사용자 세션 상태 관리
├── providers/
│   ├── aws.py           # AWS 아키텍처 + Terraform 템플릿 생성
│   └── azure.py         # Azure 아키텍처 + Terraform 템플릿 생성
├── static/
│   ├── index.html       # Wizard UI (바닐라 JS)
│   └── app.js           # 단계 진행, API 호출, 다이어그램 렌더링
└── tests/
    └── test_providers.py
```

---

## Wizard 단계 (5단계)

| 단계 | 질문 | 입력 형태 |
|------|------|-----------|
| 1 | 클라우드 제공자 선택 | 버튼 (AWS / Azure) |
| 2 | 애플리케이션 유형 | 선택 (웹앱 / API 서버 / 배치 / 데이터 파이프라인) |
| 3 | 주요 기술 스택 | 체크박스 (DB, 캐시, 메시지큐, CDN 등) |
| 4 | 규모/요구사항 | 슬라이더 + 체크박스 (예상 트래픽, HA, 멀티리전) |
| 5 | 추가 요구사항 | 자유 텍스트 (선택) |

완료 후 "아키텍처 생성" 버튼 클릭 → 결과 화면으로 전환.

---

## 데이터 흐름

```
브라우저 Wizard (5단계)
    └─ POST /generate (wizard 응답 전체)
           └─ providers/aws.py 또는 azure.py
                  ├─ 텍스트 설명 생성
                  ├─ Mermaid 다이어그램 코드 생성
                  └─ Terraform 템플릿 생성
    └─ 결과 화면 (탭 3개)
           ├─ 텍스트 설명
           ├─ 다이어그램 (Mermaid.js CDN 렌더링)
           └─ Terraform 코드 (복사 + 다운로드)
```

---

## API 엔드포인트

| 메서드 | 경로 | 역할 |
|--------|------|------|
| `GET` | `/` | index.html 서빙 |
| `POST` | `/generate` | wizard 응답 받아 아키텍처 생성 |
| `GET` | `/download/terraform` | .tf 파일 zip 다운로드 |

### `/generate` 요청/응답 스키마

**요청:**
```json
{
  "provider": "aws",
  "app_type": "web",
  "components": ["db", "cache", "cdn"],
  "scale": { "traffic": "medium", "ha": true, "multi_region": false },
  "notes": "..."
}
```

**응답:**
```json
{
  "summary": "텍스트 설명 (한국어)",
  "diagram": "graph TD\n  ...",
  "terraform": {
    "main.tf": "...",
    "variables.tf": "...",
    "outputs.tf": "..."
  }
}
```

---

## Terraform 템플릿 범위

### AWS
선택 항목에 따라 다음 리소스 조합:
- 공통: VPC, Subnet, Security Group
- 웹앱: EC2 또는 ECS + ALB
- 서버리스: Lambda + API Gateway
- DB: RDS (PostgreSQL/MySQL)
- 캐시: ElastiCache
- 스토리지: S3
- CDN: CloudFront

### Azure
- 공통: Resource Group, VNet, Subnet
- 웹앱: VM 또는 App Service + Load Balancer
- DB: Azure SQL Database
- 캐시: Azure Cache for Redis
- 스토리지: Storage Account
- CDN: Azure CDN

**실제 값 처리**: `region`, AMI ID, 인스턴스 타입 등은 모두 `variables.tf`의 `variable` 블록으로 위임. 사용자가 직접 채움.

---

## 테스트 전략

- `test_providers.py`: 각 provider 함수가 올바른 Mermaid 코드 / Terraform 블록을 반환하는지 단위 테스트
- wizard 단계 조합별 smoke test (최소 AWS 웹앱, Azure API 서버 케이스)

---

## 제외 범위

- 실제 클라우드 배포 실행 (terraform apply 미포함)
- 인증/로그인
- 결과 저장/히스토리
- GCP 지원 (추후 확장 가능 구조로 설계)
