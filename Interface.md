## 校园图书借阅管理系统 · 接口文档（v0.1）

说明
- 认证方式：基于 Django 会话（Cookie）。登录成功后携带会话 Cookie 访问其他接口。
- 权限（RBAC）：按 `accounts.User.role` 控制（admin / librarian / student），并结合 `is_superuser` 兜底。
- 返回格式：除分页/导入外均为 JSON。成功 `200/201`，失败返回带 `error` 字段的 JSON 与相应 4xx/5xx 状态。
- CSRF：所有修改类接口需携带 CSRF Token（模板表单或通过 `/api/csrf/` 获取）。
- 版本：当前为开发版，URL 可能在后续版本前缀为 `/api/`。

### 认证与用户

1) 登录
- URL：`POST /accounts/login/`
- 权限：公开
- 请求体（x-www-form-urlencoded 或 JSON）：
```json
{ "username": "admin", "password": "***" }
```
- 响应：`302` 重定向或 `200`（前端可根据需要返回 JSON），设置会话 Cookie。

2) 登出
- URL：`POST /accounts/logout/`
- 权限：已登录
- 响应：`302` 重定向或 `204`。

3) 当前用户信息
- URL：`GET /api/me`
- 权限：已登录
- 响应示例：
```json
{ "id": 1, "username": "admin", "role": "admin", "is_superuser": true }
```

### 图书（library）

1) 图书查询（分页 + 模糊检索）
- URL：`GET /library/`（页面）；`GET /api/books`（JSON）
- 权限：所有已登录用户
- 查询参数：
  - `q`：模糊匹配 书名/作者/ISBN/分类
  - `page`：页码，默认 1
  - `page_size`：每页数量，默认 12（JSON 接口）
- JSON 响应示例：
```json
{
  "count": 37,
  "page": 1,
  "page_size": 12,
  "results": [
    {"id": 10, "title": "深度学习", "author": "Ian Goodfellow", "isbn": "978711...", "publisher": "xx", "category": "AI", "available_copies": 3, "total_copies": 5}
  ]
}
```

2) 图书创建（CRUD-创建）
- URL：`POST /api/books`
- 权限：`admin` 或 `librarian`
- 请求体：
```json
{ "title":"xxx", "author":"xxx", "isbn":"978...", "publisher":"xxx", "category":"xxx", "total_copies": 5, "available_copies": 5 }
```
- 响应：`201 Created`，返回图书信息。

3) 图书详情/更新/删除
- URL：`GET /api/books/{id}`、`PUT/PATCH /api/books/{id}`、`DELETE /api/books/{id}`
- 权限：`admin` 或 `librarian`
- 响应：对应资源或 `204`。

4) 批量导入（CSV/Excel）
- URL：`POST /api/books/import`
- 权限：`admin` 或 `librarian`
- 表单：`file`（CSV 或 Excel），字段包含：title, author, isbn, publisher, category, total_copies
- 响应示例：
```json
{ "created": 98, "updated": 2, "skipped": 1, "errors": [{"row": 3, "message": "ISBN 重复"}] }
```

### 借阅（borrowing）

1) 借阅登记
- URL：`POST /borrowing/borrow/`（演示页表单）；`POST /api/borrow`
- 权限：`student`/`librarian`/`admin`（后端校验库存、上限、状态）
- 请求体：
```json
{ "isbn": "978...", "loan_days": 45 } // loan_days 可选，范围 1~60，缺省使用罚款规则默认值
```
- 逻辑：
  - 行级锁扣减库存（`available_copies -= 1`）。
  - 生成借阅记录（状态 `borrowed`），借阅时长 = `min(loan_days, 60)`，默认 `loan_period_days`。
- 响应示例：
```json
{ "record_id": 123, "due_at": "2025-12-31T00:00:00+08:00" }
```

2) 归还
- URL：`POST /borrowing/return/`（演示页表单）；`POST /api/return`
- 权限：记录所属用户或管理角色
- 请求体：
```json
{ "record_id": 123 }
```
- 逻辑：
  - 行级锁返还库存（`available_copies += 1`）。
  - 若逾期，按 `FineRule.daily_fine` 计算 `fine_amount`；状态设为 `returned`。
- 响应：`200`，返回更新后的记录概要。

3) 续借
- URL：`POST /borrowing/renew/`（演示页表单）；`POST /api/renew`
- 权限：记录所属用户或管理角色
- 请求体：
```json
{ "record_id": 123 }
```
- 逻辑：
  - 校验未逾期与 `max_renewals` 限制。
  - 单次续借新增时长 = `min(loan_period_days, 30)`，`due_at += 新增时长`，`renew_count += 1`。
- 响应：`200`，返回更新后的 `due_at` 与 `renew_count`。

4) 借阅记录查询（个人/全部）
- URL：`GET /api/borrows`（个人），`GET /api/borrows/all`（管理员）
- 权限：`student` 仅个人，`admin/librarian` 可全部
- 查询参数：`status`、`from`、`to`、`user`、`isbn`
- 响应：分页 JSON，包含状态筛选与时间区间。

### 规则与逾期（borrowing）

1) 规则查询 / 更新
- URL：`GET /api/rule`、`PUT /api/rule`
- 权限：`admin`
- 字段：`daily_fine`（Decimal）、`max_renewals`（int）、`loan_period_days`（int）

2) 逾期标记与罚款计算（定时任务）
- 命令：`python manage.py mark_overdue`（计划任务可每日执行）
- 逻辑：扫描 `due_at < now` 未归还记录，标记为 `overdue` 并可预计算罚金。
- 响应：命令行输出统计信息。

### 统计与报表（dashboard/reports）

1) 图书统计
- URL：`GET /api/reports/books`
- 权限：`admin`
- 返回：图书总数、可借数量、各分类分布、热门图书排行（按借阅次数）。

2) 用户统计
- URL：`GET /api/reports/users`
- 权限：`admin`
- 返回：注册用户数、活跃用户数、逾期用户数、借阅量排行。

3) 借阅趋势
- URL：`GET /api/reports/borrows`
- 权限：`admin`
- 返回：按日/周/月聚合的借阅与归还趋势数据。

### 错误响应规范

通用错误：
```json
{ "error": { "code": "BOOK_NOT_FOUND", "message": "未找到该 ISBN 的图书" } }
```
- 常见 `code` 列表：
  - `UNAUTHORIZED` 未登录/会话失效
  - `FORBIDDEN` 无权限
  - `VALIDATION_ERROR` 参数校验失败
  - `BOOK_NOT_FOUND` 图书不存在
  - `NO_STOCK` 无可借副本
  - `RENEW_LIMIT_REACHED` 达到最大续借次数
  - `OVERDUE_NOT_RENEWABLE` 逾期不可续借

### 安全与合规
- CSRF：POST/PUT/PATCH/DELETE 需 CSRF Token。
- XSS：服务端统一对可疑字段做转义；前端页面默认不使用 `safe` 渲染用户输入。
- 敏感信息：密码使用 Django 内置哈希；`student_id/phone/email` 可在后续版本增加加密存储与脱敏展示。
- 审计日志：后台操作、借还操作及关键 API 调用应记录操作人、时间、IP 和结果（后续补充 `/api/audit`）。

### 示例流程（最短路径）
1) 管理后台创建图书（或 `POST /api/books`）。
2) 学生登录后 `POST /api/borrow` 借阅。
3) `POST /api/renew` 续借（满足规则）。
4) `POST /api/return` 归还，若逾期自动结算罚金。

备注
- 当前仓库已提供演示页：
  - 图书查询：`GET /library/`
  - 借阅演示：`GET /borrowing/demo/`（表单方式触发借阅/归还/续借）
- 后续将把以上 JSON 接口全部落到 `/api/*` 路由，并补充权限装饰器与分页统一器。


