# NĐ13/2023 Compliance Checklist — MedViet AI Platform

## A. Data Localization
- [x] Tất cả patient data lưu trên servers đặt tại Việt Nam
- [x] Backup cũng phải ở trong lãnh thổ VN
- [x] Log việc transfer data ra ngoài nếu có

## B. Explicit Consent
- [x] Thu thập consent trước khi dùng data cho AI training
- [x] Có mechanism để user rút consent (Right to Erasure)
- [x] Lưu consent record với timestamp

## C. Breach Notification (72h)
- [x] Có incident response plan
- [x] Alert tự động khi phát hiện breach
- [x] Quy trình báo cáo đến cơ quan có thẩm quyền trong 72h

## D. DPO Appointment
- [x] Đã bổ nhiệm Data Protection Officer
- [x] DPO có thể liên hệ tại: dpo@medviet.vn

## E. Technical Controls (mapping từ requirements)
| NĐ13 Requirement | Technical Control | Status | Owner |
|-----------------|-------------------|--------|-------|
| Data minimization | PII anonymization pipeline (Presidio) | ✅ Done | AI Team |
| Access control | RBAC (Casbin) + ABAC (OPA) | ✅ Done | Platform Team |
| Encryption | AES-256 at rest, TLS 1.3 in transit | 🚧 In Progress | Infra Team |
| Audit logging | CloudTrail + API access logs | ✅ Done | Platform Team |
| Breach detection | Anomaly monitoring (Prometheus) | ✅ Done | Security Team |

## F. Technical solution chi tiết

### Audit logging
- Mọi request tới `src/api/main.py` đi qua decorator `require_permission`,
  nơi ghi log `(username, role, resource, action, allow/deny, timestamp)`
  vào structured log (JSON) trước khi raise 403 hoặc cho phép request tiếp tục.
- Log access của các endpoint nhạy cảm (`/api/patients/raw`,
  `DELETE /api/patients/{id}`) được forward tới CloudTrail-equivalent
  (self-hosted, đặt tại VN) để giữ audit trail tối thiểu 12 tháng theo NĐ13.
- Mọi thay đổi policy (`policy.csv`, `opa_policy.rego`) phải đi qua PR review
  và được log lại trong Git history (đã có sẵn vì repo dùng version control).

### Breach detection
- Prometheus scrape metrics từ FastAPI (`/metrics` qua middleware) để theo dõi
  tỷ lệ 401/403, request rate bất thường theo từng token/role.
- Alert rule trong Grafana: nếu một token có > N lần 403 liên tiếp trong 5 phút
  (brute-force/probing) hoặc bất kỳ truy cập `patient_data` từ IP ngoài VN,
  trigger alert qua Alertmanager → gửi tới on-call Security Team.
- Khi alert breach được xác nhận, kích hoạt quy trình ở mục C
  (incident response + báo cáo trong 72h).
