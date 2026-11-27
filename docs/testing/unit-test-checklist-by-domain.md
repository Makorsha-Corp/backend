# Unit Test Checklist — by Domain

> Generated 2026-09-03 from `app/` source via AST parse. Same callables as the by-layer file, regrouped by business domain so each domain's checklist can also seed **integration-test** planning.

**Total callables:** 1791. Each function appears once, under a single domain. Within a domain, files are ordered managers → services → utils → core → integrations → DAOs.

Legend: `_(private)_` leading-underscore helper · `_(async)_` coroutine · `_(dunder)_` magic method · `Lnnn` source line · ⚠️ reference scan found no use of this callable — triage before testing, see `dead-code-removal-checklist.md`.

| Domain | Files | Callables |
|---|--:|--:|
| Auth & Security | 7 | 41 |
| Workspace, Accounts & Org Structure | 25 | 164 |
| Items & Catalog | 13 | 108 |
| Inventory & Ledgers | 15 | 127 |
| Purchase Orders | 8 | 149 |
| Sales Orders & Deliveries | 10 | 100 |
| Transfer Orders | 5 | 85 |
| Work Orders | 19 | 187 |
| Expense Orders | 5 | 88 |
| Order Infrastructure & Workflow | 14 | 84 |
| Machines | 13 | 83 |
| Projects | 16 | 82 |
| Production | 13 | 125 |
| Invoicing & Accounts Receivable | 8 | 85 |
| Subscription Billing & Payment Gateway | 8 | 39 |
| Notifications & Discussions | 6 | 16 |
| Calendar | 1 | 15 |
| Attachments & Uploads | 16 | 122 |
| Help, Waitlist & Platform Admin | 6 | 35 |
| Financial Audit | 3 | 15 |
| Shared Infrastructure | 10 | 41 |

## Auth & Security (41 callables)

### Managers

#### `app/managers/profile_stamp_manager.py` (6)

#### class `ProfileStampManager`

- [ ] `ProfileStampManager._upload_env()` — L22 _(private)_
- [ ] `ProfileStampManager.build_stamp_public_id()` — L25
- [ ] `ProfileStampManager.build_stamp_asset_folder()` — L32
- [ ] `ProfileStampManager.sign_stamp_image_upload()` — L39
- [ ] `ProfileStampManager.destroy_saved_stamp_image()` — L70
- [ ] `ProfileStampManager.validate_saved_stamp_payload()` — L81

### Services

#### `app/services/auth_service.py` (15)

#### class `TokenPair`

_(no methods defined in class body)_


#### class `AuthService` (BaseService)

- [ ] `AuthService.__init__()` — L64 _(dunder)_
- [ ] `AuthService._issue_token_pair()` — L78 _(private)_
- [ ] `AuthService.register_user()` — L139
- [ ] `AuthService._register_user_only()` — L248 _(private)_
- [ ] `AuthService._register_with_invitation()` — L282 _(private)_
- [ ] `AuthService._register_with_new_workspace()` — L356 _(private)_
- [ ] `AuthService.login_user()` — L435
- [ ] `AuthService.switch_workspace()` — L474
- [ ] `AuthService.refresh_access_token()` — L531
- [ ] `AuthService.logout_session()` — L614
- [ ] `AuthService.request_password_reset()` — L663
- [ ] `AuthService.reset_password()` — L733
- [ ] `AuthService.reset_password_by_admin()` — L788
- [ ] `AuthService.validate_invitation_token()` — L880
- [ ] `AuthService.update_current_user()` — L938

### Utils

#### `app/utils/profile_auth.py` (1)

#### module-level functions

- [ ] `profile_to_auth_dict()` — L7

#### `app/utils/timezone_validate.py` (1)

#### module-level functions

- [ ] `is_valid_iana_timezone()` — L7

### Core

#### `app/core/security.py` (6)

#### module-level functions

- [ ] `create_access_token()` — L19
- [ ] `verify_password()` — L43
- [ ] `get_password_hash()` — L68
- [ ] `create_refresh_token()` — L91
- [ ] `hash_refresh_token()` — L107
- [ ] `decode_token()` — L119

### DAOs

#### `app/dao/profile.py` (3)

#### class `DAOProfile` (BaseDAO[Profile, ProfileCreate, ProfileUpdate])

- [ ] `DAOProfile.get_by_email()` — L13
- [ ] `DAOProfile.create()` — L26
- [ ] `DAOProfile.authenticate()` — L48

#### `app/dao/refresh_token.py` (9)

#### class `RefreshTokenDAO`

- [ ] `RefreshTokenDAO.get_by_hash()` — L22
- [ ] `RefreshTokenDAO.get_by_id()` — L33
- [x] `RefreshTokenDAO.list_active_for_user()` — L36 ~~[DELETED DEAD CODE]~~
- [ ] `RefreshTokenDAO.create()` — L52
- [ ] `RefreshTokenDAO.revoke()` — L81
- [ ] `RefreshTokenDAO.revoke_family()` — L95
- [ ] `RefreshTokenDAO.revoke_all_for_user()` — L112
- [ ] `RefreshTokenDAO.touch_last_used()` — L126
- [x] `RefreshTokenDAO.cleanup_expired()` — L131 ~~[DELETED DEAD CODE]~~

## Workspace, Accounts & Org Structure (164 callables)

### Managers

#### `app/managers/account_manager.py` (10)

#### class `AccountManager` (BaseManager[Account])

- [ ] `AccountManager.__init__()` — L26 _(dunder)_
- [ ] `AccountManager.create_account()` — L30
- [ ] `AccountManager.update_account()` — L105
- [ ] `AccountManager.get_account()` — L201
- [ ] `AccountManager.search_accounts()` — L227
- [ ] `AccountManager.delete_account()` — L259
- [ ] `AccountManager._assign_tags_to_account()` — L302 _(private)_
- [ ] `AccountManager.assign_tag()` — L347
- [ ] `AccountManager.unassign_tag()` — L385
- [ ] `AccountManager.get_tags_for_account()` — L410

#### `app/managers/department_manager.py` (7)

#### class `DepartmentManager` (BaseManager[Department])

- [ ] `DepartmentManager.__init__()` — L23 _(dunder)_
- [ ] `DepartmentManager.create_department()` — L27
- [ ] `DepartmentManager.update_department()` — L67
- [ ] `DepartmentManager.get_department()` — L126
- [ ] `DepartmentManager.search_departments()` — L158
- [ ] `DepartmentManager.delete_department()` — L200
- [ ] `DepartmentManager._check_name_exists()` — L245 _(private)_

#### `app/managers/factory_manager.py` (8)

#### class `FactoryManager` (BaseManager[Factory])

- [ ] `FactoryManager.__init__()` — L26 _(dunder)_
- [ ] `FactoryManager.create_factory()` — L30
- [ ] `FactoryManager.update_factory()` — L80
- [ ] `FactoryManager.get_factory()` — L150
- [ ] `FactoryManager.search_factories()` — L182
- [ ] `FactoryManager.delete_factory()` — L225
- [ ] `FactoryManager._check_name_exists()` — L270 _(private)_
- [ ] `FactoryManager._check_abbreviation_exists()` — L298 _(private)_

#### `app/managers/factory_section_manager.py` (7)

#### class `FactorySectionManager` (BaseManager[FactorySection])

- [ ] `FactorySectionManager.__init__()` — L26 _(dunder)_
- [ ] `FactorySectionManager.create_factory_section()` — L31
- [ ] `FactorySectionManager.update_factory_section()` — L91
- [ ] `FactorySectionManager.get_factory_section()` — L172
- [ ] `FactorySectionManager.search_factory_sections()` — L204
- [ ] `FactorySectionManager.delete_factory_section()` — L254
- [ ] `FactorySectionManager._check_name_exists_in_factory()` — L303 _(private)_

#### `app/managers/workspace_manager.py` (8)

#### class `WorkspaceManager` (BaseManager[Workspace])

- [ ] `WorkspaceManager.__init__()` — L46 _(dunder)_
- [ ] `WorkspaceManager.create_workspace_with_owner()` — L54
- [ ] `WorkspaceManager.add_member_to_workspace()` — L152
- [ ] `WorkspaceManager.remove_member_from_workspace()` — L234
- [ ] `WorkspaceManager.create_invitation()` — L296
- [ ] `WorkspaceManager.validate_invitation_for_user()` — L391
- [ ] `WorkspaceManager.accept_invitation()` — L444
- [ ] `WorkspaceManager.cancel_invitation()` — L501

### Services

#### `app/services/access_control_service.py` (5)

#### class `AccessControlService`

- [ ] `AccessControlService.get_controls()` — L11
- [ ] `AccessControlService.get_by_id()` — L20
- [ ] `AccessControlService.create_control()` — L24
- [ ] `AccessControlService.update_control()` — L37
- [ ] `AccessControlService.delete_control()` — L51

#### `app/services/account_service.py` (14)

#### class `AccountService` (BaseService)

- [ ] `AccountService.__init__()` — L26 _(dunder)_
- [ ] `AccountService.create_account()` — L30
- [ ] `AccountService.get_account()` — L71
- [ ] `AccountService.get_account_with_tags()` — L96
- [x] `AccountService.get_accounts()` — L159 ~~[DELETED DEAD CODE]~~
- [ ] `AccountService.get_accounts_with_tags()` — L188
- [ ] `AccountService._account_dict_with_tags()` — L264 _(private)_
- [ ] `AccountService._rollup_from_subquery_row()` — L304 _(private)_
- [ ] `AccountService.get_accounts_hub_page()` — L312
- [ ] `AccountService.update_account()` — L350
- [ ] `AccountService.get_accounts_by_tag_id()` — L400
- [ ] `AccountService.assign_tag()` — L461
- [ ] `AccountService.unassign_tag()` — L490
- [ ] `AccountService.delete_account()` — L516

#### `app/services/account_tag_service.py` (5)

#### class `AccountTagService`

- [ ] `AccountTagService.get_tags()` — L11
- [ ] `AccountTagService.get_system_tags()` — L15
- [ ] `AccountTagService.create_tag()` — L19
- [ ] `AccountTagService.update_tag()` — L50
- [ ] `AccountTagService.delete_tag()` — L68

#### `app/services/app_settings_service.py` (6)

#### class `AppSettingsService`

- [ ] `AppSettingsService.get_settings()` — L10
- [ ] `AppSettingsService.get_by_id()` — L14
- [ ] `AppSettingsService.get_by_name()` — L18
- [ ] `AppSettingsService.create_setting()` — L22
- [ ] `AppSettingsService.update_setting()` — L35
- [ ] `AppSettingsService.delete_setting()` — L49

#### `app/services/department_service.py` (6)

#### class `DepartmentService` (BaseService)

- [ ] `DepartmentService.__init__()` — L21 _(dunder)_
- [ ] `DepartmentService.create_department()` — L25
- [ ] `DepartmentService.get_department()` — L66
- [ ] `DepartmentService.get_departments()` — L88
- [ ] `DepartmentService.update_department()` — L117
- [ ] `DepartmentService.delete_department()` — L161

#### `app/services/factory_section_service.py` (6)

#### class `FactorySectionService` (BaseService)

- [ ] `FactorySectionService.__init__()` — L22 _(dunder)_
- [ ] `FactorySectionService.create_factory_section()` — L26
- [ ] `FactorySectionService.get_factory_section()` — L67
- [ ] `FactorySectionService.get_factory_sections()` — L89
- [ ] `FactorySectionService.update_factory_section()` — L121
- [ ] `FactorySectionService.delete_factory_section()` — L165

#### `app/services/factory_service.py` (6)

#### class `FactoryService` (BaseService)

- [ ] `FactoryService.__init__()` — L21 _(dunder)_
- [ ] `FactoryService.create_factory()` — L25
- [ ] `FactoryService.get_factory()` — L66
- [ ] `FactoryService.get_factories()` — L88
- [ ] `FactoryService.update_factory()` — L117
- [ ] `FactoryService.delete_factory()` — L161

#### `app/services/workspace_service.py` (15)

#### class `WorkspaceService` (BaseService)

- [ ] `WorkspaceService.__init__()` — L38 _(dunder)_
- [ ] `WorkspaceService._require_active_membership()` — L50 _(private)_
- [ ] `WorkspaceService._require_owner()` — L61 _(private)_
- [ ] `WorkspaceService.list_user_workspaces()` — L74
- [ ] `WorkspaceService.create_workspace()` — L88
- [ ] `WorkspaceService.get_workspace_with_plan()` — L110
- [ ] `WorkspaceService.update_workspace()` — L121
- [ ] `WorkspaceService.list_members()` — L147
- [ ] `WorkspaceService.update_member_role()` — L164
- [ ] `WorkspaceService.remove_member()` — L197
- [ ] `WorkspaceService.send_invitation()` — L226
- [ ] `WorkspaceService.list_invitations()` — L256
- [ ] `WorkspaceService.accept_invitation()` — L279
- [ ] `WorkspaceService.cancel_invitation()` — L319
- [ ] `WorkspaceService.get_my_invitations()` — L344

### DAOs

#### `app/dao/access_control.py` (2)

#### class `DAOAccessControl` (BaseDAO[AccessControl, AccessControlCreate, AccessControlUpdate])

- [ ] `DAOAccessControl.get_by_role()` — L18
- [ ] `DAOAccessControl.get_by_type()` — L49

#### `app/dao/account.py` (7)

#### class `AccountDAO` (BaseDAO[Account, AccountCreate, AccountUpdate])

- [ ] `AccountDAO.search_by_name_in_workspace()` — L14
- [x] `AccountDAO.get_by_account_code_in_workspace()` — L43 ~~[DELETED DEAD CODE]~~
- [x] `AccountDAO.get_active_accounts_in_workspace()` — L67 ~~[DELETED DEAD CODE]~~
- [ ] `AccountDAO.get_accounts_in_workspace()` — L94
- [ ] `AccountDAO.count_active_accounts()` — L139
- [ ] `AccountDAO.get_accounts_by_tag_id()` — L150
- [x] `AccountDAO.get_accounts_with_invoices_enabled()` — L188 ~~[DELETED DEAD CODE]~~

#### `app/dao/account_tag.py` (5)

#### class `AccountTagDAO` (BaseDAO[AccountTag, AccountTagCreate, AccountTagUpdate])

- [ ] `AccountTagDAO.get_by_tag_code_in_workspace()` — L12
- [ ] `AccountTagDAO.get_active_tags_in_workspace()` — L35
- [ ] `AccountTagDAO.get_system_tags_in_workspace()` — L61
- [ ] `AccountTagDAO.increment_usage_count()` — L83
- [ ] `AccountTagDAO.decrement_usage_count()` — L103

#### `app/dao/account_tag_assignment.py` (7)

#### class `AccountTagAssignmentDAO` (BaseDAO[AccountTagAssignment, AccountTagAssignmentCreate, AccountTagAssignmentCreate])

- [ ] `AccountTagAssignmentDAO.get_tags_for_account()` — L24
- [x] `AccountTagAssignmentDAO.get_accounts_for_tag()` — L48 ~~[DELETED DEAD CODE]~~
- [ ] `AccountTagAssignmentDAO.get_assignment()` — L75
- [ ] `AccountTagAssignmentDAO.assignment_exists()` — L100
- [ ] `AccountTagAssignmentDAO.delete_assignment()` — L120
- [ ] `AccountTagAssignmentDAO.remove_all_tags_from_account()` — L144

#### module-level functions

- [ ] `get_account_tag_dao()` — L12

#### `app/dao/app_settings.py` (1)

#### class `DAOAppSettings` (BaseDAO[AppSettings, AppSettingsCreate, AppSettingsUpdate])

- [ ] `DAOAppSettings.get_by_name()` — L18

#### `app/dao/department.py` (3)

#### class `DAODepartment` (BaseDAO[Department, DepartmentCreate, DepartmentUpdate])

- [x] `DAODepartment.get_active_departments()` — L26 ~~[DELETED DEAD CODE]~~
- [ ] `DAODepartment.soft_delete()` — L53
- [ ] `DAODepartment.restore()` — L74

#### `app/dao/factory.py` (5)

#### class `DAOFactory` (BaseDAO[Factory, FactoryCreate, FactoryUpdate])

- [ ] `DAOFactory.get_by_workspace()` — L20
- [ ] `DAOFactory.get_by_id_and_workspace()` — L43
- [ ] `DAOFactory.get_active_factories()` — L66
- [ ] `DAOFactory.soft_delete()` — L93
- [ ] `DAOFactory.restore()` — L114

#### `app/dao/factory_section.py` (3)

#### class `DAOFactorySection` (BaseDAO[FactorySection, FactorySectionCreate, FactorySectionUpdate])

- [ ] `DAOFactorySection.get_by_factory()` — L19
- [ ] `DAOFactorySection.soft_delete()` — L46
- [ ] `DAOFactorySection.restore()` — L67

#### `app/dao/workspace.py` (5)

#### class `WorkspaceDAO` (BaseDAO[Workspace, WorkspaceCreate, WorkspaceUpdate])

- [ ] `WorkspaceDAO.get_by_slug()` — L12
- [x] `WorkspaceDAO.get_by_owner()` — L16 ~~[DELETED DEAD CODE]~~
- [x] `WorkspaceDAO.increment_usage()` — L24 ~~[DELETED DEAD CODE]~~
- [x] `WorkspaceDAO.decrement_usage()` — L42 ~~[DELETED DEAD CODE]~~
- [x] `WorkspaceDAO.check_limit()` — L60 ~~[DELETED DEAD CODE]~~

#### `app/dao/workspace_audit_log.py` (4)

#### class `WorkspaceAuditLogDAO` (BaseDAO[WorkspaceAuditLog, WorkspaceAuditLogCreate, dict])

- [x] `WorkspaceAuditLogDAO.get_workspace_logs()` — L14 ~~[DELETED DEAD CODE]~~
- [x] `WorkspaceAuditLogDAO.get_user_logs()` — L44 ~~[DELETED DEAD CODE]~~
- [x] `WorkspaceAuditLogDAO.get_logs_by_action()` — L65 ~~[DELETED DEAD CODE]~~
- [ ] `WorkspaceAuditLogDAO.log_action()` — L87

#### `app/dao/workspace_invitation.py` (10)

#### class `WorkspaceInvitationDAO` (BaseDAO[WorkspaceInvitation, WorkspaceInvitationCreate, dict])

- [ ] `WorkspaceInvitationDAO.get_by_token()` — L14
- [x] `WorkspaceInvitationDAO.get_by_workspace_and_email()` — L18 ~~[DELETED DEAD CODE]~~
- [ ] `WorkspaceInvitationDAO.get_pending_invitations()` — L31
- [ ] `WorkspaceInvitationDAO.get_user_invitations()` — L45
- [x] `WorkspaceInvitationDAO.mark_as_accepted()` — L57 ~~[DELETED DEAD CODE]~~
- [x] `WorkspaceInvitationDAO.mark_as_expired()` — L66 ~~[DELETED DEAD CODE]~~
- [x] `WorkspaceInvitationDAO.mark_as_cancelled()` — L74 ~~[DELETED DEAD CODE]~~
- [ ] `WorkspaceInvitationDAO.count_pending_invitations()` — L82
- [ ] `WorkspaceInvitationDAO.get_all_invitations()` — L94
- [x] `WorkspaceInvitationDAO.cleanup_expired_invitations()` — L104 ~~[DELETED DEAD CODE]~~

#### `app/dao/workspace_member.py` (9)

#### class `WorkspaceMemberDAO` (BaseDAO[WorkspaceMember, WorkspaceMemberCreate, WorkspaceMemberUpdate])

- [ ] `WorkspaceMemberDAO.get_by_workspace_and_user()` — L12
- [x] `WorkspaceMemberDAO.get_user_workspaces()` — L25 ~~[DELETED DEAD CODE]~~
- [ ] `WorkspaceMemberDAO.get_by_user()` — L36
- [ ] `WorkspaceMemberDAO.get_workspace_members()` — L44
- [x] `WorkspaceMemberDAO.get_workspace_members_count()` — L55 ~~[DELETED DEAD CODE]~~
- [x] `WorkspaceMemberDAO.update_role()` — L66 ~~[DELETED DEAD CODE]~~
- [ ] `WorkspaceMemberDAO.get_by_workspace()` — L80
- [ ] `WorkspaceMemberDAO.count_active_members()` — L84
- [ ] `WorkspaceMemberDAO.has_access()` — L95

## Items & Catalog (108 callables)

### Managers

#### `app/managers/item_manager.py` (13)

#### class `ItemManager` (BaseManager[Item])

- [ ] `ItemManager.__init__()` — L24 _(dunder)_
- [ ] `ItemManager.create_item()` — L28
- [ ] `ItemManager.update_item()` — L74
- [ ] `ItemManager.get_item()` — L147
- [ ] `ItemManager.search_items()` — L173
- [ ] `ItemManager.list_items_filtered()` — L210
- [ ] `ItemManager.count_items_filtered()` — L231
- [ ] `ItemManager.distinct_units()` — L248
- [ ] `ItemManager.find_similar_items()` — L251
- [ ] `ItemManager.delete_item()` — L289
- [ ] `ItemManager._assign_tags_to_item()` — L324 _(private)_
- [ ] `ItemManager.get_tags_for_item()` — L369
- [ ] `ItemManager.get_tags_for_items()` — L390

#### `app/managers/product_manager.py` (10)

#### class `ProductManager` (BaseManager[Product])

- [ ] `ProductManager.__init__()` — L31 _(dunder)_
- [ ] `ProductManager.create_product()` — L36
- [ ] `ProductManager.update_product()` — L89
- [ ] `ProductManager.get_product()` — L140
- [ ] `ProductManager.list_products()` — L147
- [ ] `ProductManager.delete_product()` — L161
- [ ] `ProductManager.apply_production_output()` — L170
- [ ] `ProductManager.apply_sale_deduction()` — L254
- [ ] `ProductManager.apply_sale_return()` — L325

#### module-level functions

- [ ] `_quantity_to_int()` — L15 _(private)_

### Services

#### `app/services/item_orders_service.py` (9)

#### class `ItemOrdersService`

- [ ] `ItemOrdersService.get_orders_for_item()` — L110
- [ ] `ItemOrdersService._purchase_rows()` — L182 _(private)_
- [ ] `ItemOrdersService._transfer_rows()` — L279 _(private)_
- [ ] `ItemOrdersService._sales_rows()` — L336 _(private)_
- [ ] `ItemOrdersService._work_rows()` — L405 _(private)_

#### module-level functions

- [ ] `_dec()` — L30 _(private)_
- [ ] `_in_date_range()` — L36 _(private)_
- [ ] `_weighted_unit_price()` — L40 _(private)_
- [ ] `_build_po_destination_labels()` — L46 _(private)_

#### `app/services/item_service.py` (10)

#### class `ItemService` (BaseService)

- [ ] `ItemService.__init__()` — L24 _(dunder)_
- [ ] `ItemService.create_item()` — L28
- [ ] `ItemService.get_item()` — L69
- [ ] `ItemService.get_items()` — L94
- [x] `ItemService.get_items_with_tags()` — L123 ~~[DELETED DEAD CODE]~~
- [ ] `ItemService.get_items_page()` — L146
- [ ] `ItemService.get_distinct_units()` — L218
- [ ] `ItemService.get_similar_items()` — L221
- [ ] `ItemService.update_item()` — L243
- [ ] `ItemService.delete_item()` — L293

#### `app/services/item_summary_service.py` (22)

#### class `ItemSummaryService`

- [ ] `ItemSummaryService.get_summary()` — L85
- [ ] `ItemSummaryService._factory_name_map()` — L189 _(private)_
- [ ] `ItemSummaryService._machine_name_map()` — L193 _(private)_
- [ ] `ItemSummaryService._machine_location_map()` — L197 _(private)_
- [ ] `ItemSummaryService._inventory_rows()` — L227 _(private)_
- [ ] `ItemSummaryService._product_rows()` — L266 _(private)_
- [ ] `ItemSummaryService._machine_placements()` — L300 _(private)_
- [ ] `ItemSummaryService._order_stats_for_item()` — L341 _(private)_
- [ ] `ItemSummaryService._pricing_snapshot_from_po_lines()` — L414 _(private)_
- [ ] `ItemSummaryService._pricing()` — L435 _(private)_
- [ ] `ItemSummaryService._supplier_stats()` — L510 _(private)_
- [ ] `ItemSummaryService._supplier_period_snapshot()` — L549 _(private)_
- [ ] `ItemSummaryService._supplier_rows_from_po_lines()` — L572 _(private)_
- [ ] `ItemSummaryService._pick_cheapest_supplier()` — L631 _(private)_
- [ ] `ItemSummaryService._pick_most_frequent_supplier()` — L645 _(private)_
- [ ] `ItemSummaryService._usage()` — L658 _(private)_
- [ ] `ItemSummaryService._resolve_order_link()` — L821 _(private)_
- [ ] `ItemSummaryService._resolve_order_number()` — L854 _(private)_
- [ ] `ItemSummaryService._activity_from_ledger()` — L879 _(private)_
- [ ] `ItemSummaryService._recent_activity()` — L922 _(private)_

#### module-level functions

- [ ] `_dec()` — L72 _(private)_
- [ ] `_est_value()` — L78 _(private)_

#### `app/services/item_tag_service.py` (5)

#### class `ItemTagService`

- [ ] `ItemTagService.get_tags()` — L12
- [ ] `ItemTagService.get_system_tags()` — L22
- [ ] `ItemTagService.create_tag()` — L26
- [ ] `ItemTagService.update_tag()` — L57
- [ ] `ItemTagService.delete_tag()` — L75

#### `app/services/product_service.py` (7)

#### class `ProductService` (BaseService)

- [ ] `ProductService.__init__()` — L17 _(dunder)_
- [ ] `ProductService.create_product()` — L22
- [ ] `ProductService.update_product()` — L35
- [ ] `ProductService.get_product()` — L48
- [ ] `ProductService.list_products()` — L51
- [ ] `ProductService.delete_product()` — L64
- [ ] `ProductService.list_ledger()` — L75

### Utils

#### `app/utils/item_name_normalize.py` (1)

#### module-level functions

- [ ] `normalize_item_name()` — L13

#### `app/utils/order_catalog_items.py` (3)

#### module-level functions

- [ ] `assert_unique_catalog_item_ids()` — L10
- [ ] `catalog_item_already_on_order_detail()` — L37
- [ ] `assert_meets_minimum_order_quantities()` — L45

### DAOs

#### `app/dao/item.py` (8)

#### class `ItemDAO` (BaseDAO[Item, ItemCreate, ItemUpdate])

- [ ] `ItemDAO.search_by_name_in_workspace()` — L72
- [x] `ItemDAO.get_by_sku_in_workspace()` — L100 ~~[DELETED DEAD CODE]~~
- [ ] `ItemDAO.get_active_items_in_workspace()` — L123
- [ ] `ItemDAO.list_active_items_filtered()` — L149
- [ ] `ItemDAO.count_active_items_filtered()` — L170
- [ ] `ItemDAO.distinct_units_in_workspace()` — L192
- [ ] `ItemDAO.find_similar_by_name_in_workspace()` — L205

#### module-level functions

- [ ] `_apply_item_catalog_filters()` — L17 _(private)_

#### `app/dao/item_tag.py` (6)

#### class `ItemTagDAO` (BaseDAO[ItemTag, ItemTagCreate, ItemTagUpdate])

- [ ] `ItemTagDAO.get_by_code_in_workspace()` — L12
- [ ] `ItemTagDAO.get_system_tags_in_workspace()` — L35
- [x] `ItemTagDAO.get_user_tags_in_workspace()` — L58 ~~[DELETED DEAD CODE]~~
- [ ] `ItemTagDAO.get_active_tags_in_workspace()` — L81
- [ ] `ItemTagDAO.increment_usage_count()` — L104
- [ ] `ItemTagDAO.decrement_usage_count()` — L124

#### `app/dao/item_tag_assignment.py` (8)

#### class `ItemTagAssignmentDAO` (BaseDAO[ItemTagAssignment, ItemTagAssignmentCreate, ItemTagAssignmentResponse])

- [ ] `ItemTagAssignmentDAO.get_tags_for_items()` — L15
- [ ] `ItemTagAssignmentDAO.get_tags_for_item()` — L44
- [x] `ItemTagAssignmentDAO.get_items_with_tag()` — L69 ~~[DELETED DEAD CODE]~~
- [x] `ItemTagAssignmentDAO.get_items_with_tags()` — L97 ~~[DELETED DEAD CODE]~~
- [ ] `ItemTagAssignmentDAO.assignment_exists()` — L131
- [x] `ItemTagAssignmentDAO.remove_assignment()` — L156 ~~[DELETED DEAD CODE]~~
- [ ] `ItemTagAssignmentDAO.count_active_items_per_tag()` — L187
- [ ] `ItemTagAssignmentDAO.remove_all_tags_from_item()` — L208

#### `app/dao/product.py` (6)

#### class `ProductDAO` (BaseDAO[Product, ProductCreate, ProductUpdate])

- [ ] `ProductDAO.get_by_workspace()` — L15
- [ ] `ProductDAO.get_by_id_and_workspace()` — L32
- [ ] `ProductDAO.get_by_factory_item_available()` — L41
- [ ] `ProductDAO.get_by_item()` — L54
- [ ] `ProductDAO.soft_delete()` — L64
- [ ] `ProductDAO.restore()` — L75

## Inventory & Ledgers (127 callables)

### Managers

#### `app/managers/inventory_manager.py` (10)

#### class `InventoryManager` (BaseManager[Inventory])

- [ ] `InventoryManager.__init__()` — L25 _(dunder)_
- [ ] `InventoryManager.create_inventory()` — L30
- [ ] `InventoryManager.update_inventory()` — L84
- [ ] `InventoryManager.get_inventory()` — L136
- [ ] `InventoryManager.list_inventory()` — L143
- [ ] `InventoryManager.get_inventory_page()` — L156
- [ ] `InventoryManager.get_inventory_stats()` — L197
- [ ] `InventoryManager.delete_inventory()` — L231
- [ ] `InventoryManager.get_incoming_summary_for_factory()` — L268
- [ ] `InventoryManager.get_incoming_summary()` — L375

#### `app/managers/inventory_movements.py` (11)

#### module-level functions

- [ ] `item_name()` — L23
- [ ] `weighted_avg_price()` — L28
- [ ] `inventory_type_for_location()` — L42
- [ ] `_storage_out()` — L48 _(private)_
- [ ] `_storage_in()` — L116 _(private)_
- [ ] `ensure_machine_item()` — L179
- [ ] `get_machine_unit_cost()` — L196
- [ ] `_machine_out()` — L205 _(private)_
- [ ] `_machine_in()` — L282 _(private)_
- [ ] `post_stock_out()` — L354
- [ ] `post_stock_in()` — L412

#### `app/managers/ledger_manager.py` (12)

#### class `LedgerManager` (BaseManager[MachineItemLedger])

- [ ] `LedgerManager.__init__()` — L35 _(dunder)_
- [ ] `LedgerManager.get_machine_ledger()` — L50
- [ ] `LedgerManager.get_machine_balance()` — L109
- [ ] `LedgerManager.reconcile_machine_item()` — L135
- [ ] `LedgerManager.get_project_component_ledger()` — L277
- [ ] `LedgerManager.calculate_project_component_total_cost()` — L318
- [ ] `LedgerManager.get_inventory_ledger()` — L349
- [ ] `LedgerManager.get_inventory_balance()` — L417
- [ ] `LedgerManager.reconcile_inventory()` — L447
- [ ] `LedgerManager.get_attachment_ledger()` — L563
- [ ] `LedgerManager.get_item_movement_summary()` — L592
- [ ] `LedgerManager.get_transactions_by_user()` — L646

#### `app/managers/po_machine_inventory.py` (5)

#### module-level functions

- [ ] `_quantity_to_int()` — L20 _(private)_
- [ ] `_weighted_avg_price()` — L38 _(private)_
- [ ] `_ensure_machine_item()` — L52 _(private)_
- [ ] `_ledger_exists_for_source()` — L71 _(private)_
- [x] `post_purchase_order_to_machine()` — L86 ~~[DELETED DEAD CODE]~~

#### `app/managers/po_receive_inventory.py` (10)

#### module-level functions

- [ ] `_delta_to_int()` — L22 _(private)_
- [ ] `_ledger_exists()` — L37 _(private)_
- [ ] `_storage_ledger_exists()` — L57 _(private)_
- [ ] `_machine_ledger_exists()` — L63 _(private)_
- [ ] `_location_for_po()` — L73 _(private)_
- [ ] `_post_event_item_delta()` — L81 _(private)_
- [ ] `post_receive_event_inventory()` — L166
- [ ] `_reverse_event_item_posting()` — L188 _(private)_
- [ ] `_reverse_legacy_line_posting()` — L288 _(private)_
- [ ] `reverse_po_receive_inventory()` — L368

#### `app/managers/po_return_inventory.py` (5)

#### module-level functions

- [ ] `_machine_ledger_exists()` — L18 _(private)_
- [ ] `_storage_ledger_exists()` — L31 _(private)_
- [ ] `_location_for_po()` — L37 _(private)_
- [ ] `_quantity_to_int()` — L45 _(private)_
- [ ] `post_purchase_return_inventory()` — L54

#### `app/managers/po_storage_inventory.py` (3)

#### module-level functions

- [ ] `_quantity_to_int()` — L18 _(private)_
- [ ] `_weighted_avg_price()` — L36 _(private)_
- [x] `post_purchase_order_to_storage()` — L50 ~~[DELETED DEAD CODE]~~

#### `app/managers/to_inventory.py` (5)

#### module-level functions

- [ ] `_quantity_to_int()` — L21 _(private)_
- [ ] `_line_already_posted()` — L39 _(private)_
- [ ] `_post_location_out()` — L59 _(private)_
- [ ] `_post_location_in()` — L98 _(private)_
- [ ] `post_transfer_order_inventory()` — L144

### Services

#### `app/services/inventory_service.py` (9)

#### class `InventoryService` (BaseService)

- [ ] `InventoryService.__init__()` — L16 _(dunder)_
- [ ] `InventoryService.create_inventory()` — L20
- [ ] `InventoryService.update_inventory()` — L33
- [ ] `InventoryService.get_inventory()` — L46
- [ ] `InventoryService.list_inventory()` — L49
- [ ] `InventoryService.get_inventory_page()` — L61
- [ ] `InventoryService.get_inventory_stats()` — L86
- [ ] `InventoryService.get_incoming_summary()` — L107
- [ ] `InventoryService.delete_inventory()` — L114

#### `app/services/ledger_service.py` (13)

#### class `LedgerService` (BaseService)

- [ ] `LedgerService.__init__()` — L29 _(dunder)_
- [ ] `LedgerService.get_machine_ledger()` — L37
- [ ] `LedgerService.get_machine_balance()` — L62
- [ ] `LedgerService.reconcile_machine_item()` — L83
- [ ] `LedgerService.get_project_component_ledger()` — L129
- [ ] `LedgerService.get_project_component_total_cost()` — L153
- [ ] `LedgerService.get_inventory_ledger()` — L179
- [ ] `LedgerService.get_inventory_balance()` — L211
- [ ] `LedgerService.reconcile_inventory()` — L235
- [ ] `LedgerService.get_attachment_ledger()` — L283
- [ ] `LedgerService.get_item_movement_summary()` — L312
- [ ] `LedgerService.get_transactions_by_user()` — L333
- [ ] `LedgerService.get_transactions_by_order()` — L354

### DAOs

#### `app/dao/inventory.py` (13)

#### class `InventoryDAO` (BaseDAO[Inventory, InventoryCreate, InventoryUpdate])

- [ ] `InventoryDAO._filtered_query()` — L20 _(private)_
- [ ] `InventoryDAO.list_filtered()` — L58
- [ ] `InventoryDAO.count_filtered()` — L87
- [ ] `InventoryDAO.stats_filtered()` — L108
- [ ] `InventoryDAO.get_by_workspace()` — L144
- [ ] `InventoryDAO.get_by_id_and_workspace()` — L161
- [ ] `InventoryDAO.get_by_factory_item_type()` — L170
- [ ] `InventoryDAO._get_any_by_factory_item_type()` — L183 _(private)_
- [ ] `InventoryDAO.sync_snapshot_from_ledger()` — L195
- [ ] `InventoryDAO.ensure_for_factory_item_type()` — L227
- [ ] `InventoryDAO.get_by_item()` — L293
- [ ] `InventoryDAO.soft_delete()` — L307
- [ ] `InventoryDAO.restore()` — L318

#### `app/dao/inventory_ledger.py` (10)

#### class `InventoryLedgerDAO` (BaseDAO[InventoryLedger, InventoryLedgerCreate, InventoryLedgerUpdate])

- [ ] `InventoryLedgerDAO.get_by_workspace()` — L24
- [ ] `InventoryLedgerDAO.get_by_id_and_workspace()` — L43
- [x] `InventoryLedgerDAO.get_by_factory_and_item()` — L52 ~~[DELETED DEAD CODE]~~
- [ ] `InventoryLedgerDAO.get_by_transaction_type()` — L72
- [ ] `InventoryLedgerDAO.get_by_date_range()` — L97
- [ ] `InventoryLedgerDAO.get_by_order()` — L124
- [ ] `InventoryLedgerDAO.get_by_performer()` — L138
- [ ] `InventoryLedgerDAO.calculate_balance()` — L155
- [ ] `InventoryLedgerDAO.get_latest_entry()` — L179
- [ ] `InventoryLedgerDAO.exists_for_source()` — L196

#### `app/dao/machine_item_ledger.py` (9)

#### class `MachineItemLedgerDAO` (BaseDAO[MachineItemLedger, MachineItemLedgerCreate, MachineItemLedgerUpdate])

- [ ] `MachineItemLedgerDAO.get_by_item()` — L14
- [ ] `MachineItemLedgerDAO.get_by_machine_and_item()` — L30
- [ ] `MachineItemLedgerDAO.get_by_transaction_type()` — L61
- [ ] `MachineItemLedgerDAO.get_by_order()` — L87
- [ ] `MachineItemLedgerDAO.get_by_date_range()` — L111
- [ ] `MachineItemLedgerDAO.get_by_machine()` — L138
- [x] `MachineItemLedgerDAO.get_consumption_entries()` — L167 ~~[DELETED DEAD CODE]~~
- [ ] `MachineItemLedgerDAO.calculate_balance()` — L197
- [ ] `MachineItemLedgerDAO.get_latest_entry()` — L227

#### `app/dao/product_ledger.py` (3)

#### class `ProductLedgerDAO` (BaseDAO[ProductLedger, ProductLedgerCreate, ProductLedgerUpdate])

- [ ] `ProductLedgerDAO.get_by_workspace()` — L17
- [ ] `ProductLedgerDAO.exists_for_production_batch()` — L45
- [ ] `ProductLedgerDAO.get_by_id_and_workspace()` — L60

#### `app/dao/project_component_item_ledger.py` (9)

#### class `ProjectComponentItemLedgerDAO` (BaseDAO[ProjectComponentItemLedger, ProjectComponentItemLedgerCreate, ProjectComponentItemLedgerUpdate])

- [ ] `ProjectComponentItemLedgerDAO.get_by_component_and_item()` — L14
- [ ] `ProjectComponentItemLedgerDAO.get_by_component()` — L45
- [ ] `ProjectComponentItemLedgerDAO.get_by_transaction_type()` — L74
- [ ] `ProjectComponentItemLedgerDAO.get_by_order()` — L103
- [ ] `ProjectComponentItemLedgerDAO.get_by_date_range()` — L127
- [x] `ProjectComponentItemLedgerDAO.get_consumption_entries()` — L158 ~~[DELETED DEAD CODE]~~
- [ ] `ProjectComponentItemLedgerDAO.calculate_balance()` — L188
- [ ] `ProjectComponentItemLedgerDAO.get_latest_entry()` — L218
- [ ] `ProjectComponentItemLedgerDAO.calculate_total_cost_for_component()` — L244

## Purchase Orders (149 callables)

### Managers

#### `app/managers/purchase_order_manager.py` (66)

#### class `PurchaseOrderManager` (BaseManager[PurchaseOrder])

- [ ] `PurchaseOrderManager.__init__()` — L102 _(dunder)_
- [ ] `PurchaseOrderManager.get_po_by_invoice_id()` — L109
- [ ] `PurchaseOrderManager.is_po_financially_locked()` — L116
- [ ] `PurchaseOrderManager.unlink_invoice_from_po()` — L127
- [ ] `PurchaseOrderManager.unconfirm_sections_after_invoice_void()` — L149
- [ ] `PurchaseOrderManager.reset_approvals()` — L175
- [ ] `PurchaseOrderManager._ensure_po_stage_statuses()` — L200 _(private)_
- [ ] `PurchaseOrderManager._raise_po_workflow_setup_error()` — L210 _(private)_
- [ ] `PurchaseOrderManager._resolve_po_stage_status_id()` — L232 _(private)_
- [ ] `PurchaseOrderManager._resolve_po_workflow_id()` — L248 _(private)_
- [ ] `PurchaseOrderManager._all_items_fully_received()` — L255 _(private)_
- [ ] `PurchaseOrderManager._current_stage_name()` — L264 _(private)_
- [ ] `PurchaseOrderManager._invoice_payment_status()` — L274 _(private)_
- [ ] `PurchaseOrderManager.sync_po_for_linked_invoice()` — L282
- [ ] `PurchaseOrderManager.sync_po_paid()` — L293
- [ ] `PurchaseOrderManager._is_po_complete_stage()` — L318 _(private)_
- [ ] `PurchaseOrderManager._derive_po_stage_name()` — L321 _(private)_
- [ ] `PurchaseOrderManager.sync_po_stage()` — L335
- [ ] `PurchaseOrderManager.mark_order_complete()` — L392
- [ ] `PurchaseOrderManager.reopen_for_return()` — L444
- [ ] `PurchaseOrderManager.create_purchase_order()` — L467
- [ ] `PurchaseOrderManager.update_purchase_order()` — L535
- [ ] `PurchaseOrderManager._format_scalar_value()` — L624 _(private)_
- [ ] `PurchaseOrderManager._format_destination_id()` — L638 _(private)_
- [ ] `PurchaseOrderManager._format_field_value()` — L661 _(private)_
- [ ] `PurchaseOrderManager._collect_field_changes()` — L692 _(private)_
- [ ] `PurchaseOrderManager._collect_item_field_changes()` — L723 _(private)_
- [ ] `PurchaseOrderManager._log_field_change_event()` — L742 _(private)_
- [ ] `PurchaseOrderManager._log_section_field_updates()` — L758 _(private)_
- [ ] `PurchaseOrderManager._log_admin_field_updates()` — L785 _(private)_
- [ ] `PurchaseOrderManager._confirmed_supplier_update_fields()` — L812 _(private)_
- [ ] `PurchaseOrderManager._confirmed_detail_update_fields()` — L819 _(private)_
- [ ] `PurchaseOrderManager._items_structure_confirmed()` — L826 _(private)_
- [x] `PurchaseOrderManager.details_complete_for_invoice()` — L829 ~~[DELETED DEAD CODE]~~
- [ ] `PurchaseOrderManager._base_sections_confirmed()` — L837 _(private)_
- [x] `PurchaseOrderManager._all_sections_confirmed()` — L844 _(private)_ ~~[DELETED DEAD CODE]~~
- [ ] `PurchaseOrderManager._validate_section_confirm()` — L850 _(private)_
- [ ] `PurchaseOrderManager.apply_post_invoice_confirms()` — L900
- [ ] `PurchaseOrderManager.get_purchase_order()` — L934
- [ ] `PurchaseOrderManager.list_purchase_orders()` — L940
- [ ] `PurchaseOrderManager.list_purchase_orders_for_hub()` — L953
- [ ] `PurchaseOrderManager.count_purchase_orders_for_hub()` — L970
- [ ] `PurchaseOrderManager.purchase_order_hub_stats()` — L975
- [ ] `PurchaseOrderManager.list_purchase_orders_recent_for_hub()` — L980
- [ ] `PurchaseOrderManager.purchase_order_pending_highlights_for_hub()` — L987
- [ ] `PurchaseOrderManager.delete_purchase_order()` — L994
- [ ] `PurchaseOrderManager._quantity_received_decimal()` — L1033 _(private)_
- [ ] `PurchaseOrderManager._validate_ordered_vs_received()` — L1040 _(private)_
- [ ] `PurchaseOrderManager._ensure_catalog_item_not_on_po()` — L1054 _(private)_
- [ ] `PurchaseOrderManager.add_item()` — L1076
- [ ] `PurchaseOrderManager.update_item()` — L1131
- [ ] `PurchaseOrderManager.remove_item()` — L1305
- [ ] `PurchaseOrderManager.sync_items()` — L1343
- [ ] `PurchaseOrderManager.get_items()` — L1474
- [ ] `PurchaseOrderManager._recalc_totals()` — L1477 _(private)_
- [ ] `PurchaseOrderManager.list_approvers()` — L1486
- [ ] `PurchaseOrderManager.approval_summary()` — L1501
- [ ] `PurchaseOrderManager.approvals_met()` — L1515
- [ ] `PurchaseOrderManager.add_approver()` — L1518
- [ ] `PurchaseOrderManager.remove_approver()` — L1557
- [ ] `PurchaseOrderManager.set_approval()` — L1577
- [ ] `PurchaseOrderManager.log_event()` — L1624
- [ ] `PurchaseOrderManager.list_events()` — L1641

#### module-level functions

- [ ] `_parse_unit_price()` — L83 _(private)_
- [ ] `_line_subtotal()` — L89 _(private)_
- [ ] `_all_items_have_positive_unit_price()` — L93 _(private)_

#### `app/managers/purchase_order_return_manager.py` (6)

#### class `PurchaseOrderReturnManager` (BaseManager[PurchaseOrderReturn])

- [ ] `PurchaseOrderReturnManager.__init__()` — L17 _(dunder)_
- [ ] `PurchaseOrderReturnManager.has_open_return()` — L23
- [ ] `PurchaseOrderReturnManager.validate_and_build_items()` — L28
- [ ] `PurchaseOrderReturnManager.get_return()` — L70
- [ ] `PurchaseOrderReturnManager.list_returns()` — L80
- [ ] `PurchaseOrderReturnManager.sync_return_paid()` — L87

### Services

#### `app/services/purchase_order_item_insights_service.py` (7)

#### class `_HistoryLine`

_(no methods defined in class body)_


#### class `PurchaseOrderItemInsightsService`

- [ ] `PurchaseOrderItemInsightsService.get_item_price_insights()` — L56
- [ ] `PurchaseOrderItemInsightsService._fetch_history_lines()` — L115 _(private)_
- [ ] `PurchaseOrderItemInsightsService._pick_last_ordered()` — L166 _(private)_
- [ ] `PurchaseOrderItemInsightsService._pick_min_price_ref()` — L180 _(private)_
- [ ] `PurchaseOrderItemInsightsService._pick_avg_supplier_lowest()` — L212 _(private)_

#### module-level functions

- [ ] `_dec()` — L25 _(private)_
- [ ] `_to_ref()` — L44 _(private)_

#### `app/services/purchase_order_service.py` (42)

#### class `PurchaseOrderService` (BaseService)

- [ ] `PurchaseOrderService.__init__()` — L54 _(dunder)_
- [ ] `PurchaseOrderService._integrity_context()` — L59 _(private)_
- [ ] `PurchaseOrderService._handle_item_integrity_error()` — L66 _(private)_
- [ ] `PurchaseOrderService._build_invoice_items_from_po()` — L147 _(private)_
- [ ] `PurchaseOrderService._delete_linked_draft_invoice_for_po()` — L164 _(private)_
- [ ] `PurchaseOrderService._sync_draft_invoice_for_po()` — L187 _(private)_
- [ ] `PurchaseOrderService._emit_po_invoice_draft_notification()` — L318 _(private)_
- [ ] `PurchaseOrderService.create_purchase_order()` — L339
- [ ] `PurchaseOrderService.update_purchase_order()` — L381
- [ ] `PurchaseOrderService.get_purchase_order()` — L423
- [ ] `PurchaseOrderService.mark_order_complete()` — L431
- [ ] `PurchaseOrderService.list_purchase_orders()` — L448
- [ ] `PurchaseOrderService._hub_filter_kwargs()` — L465 _(private)_
- [ ] `PurchaseOrderService._prepare_listed_orders()` — L494 _(private)_
- [ ] `PurchaseOrderService.list_purchase_orders_page()` — L504
- [ ] `PurchaseOrderService.get_purchase_order_hub_stats()` — L551
- [ ] `PurchaseOrderService._attach_invoice_payment_status()` — L618 _(private)_
- [ ] `PurchaseOrderService._attach_item_summaries()` — L634 _(private)_
- [ ] `PurchaseOrderService.create_receive_event()` — L659
- [ ] `PurchaseOrderService.list_receive_events()` — L788
- [ ] `PurchaseOrderService._build_receive_event_response()` — L801 _(private)_
- [ ] `PurchaseOrderService._attach_return_invoice_for_po()` — L829 _(private)_
- [ ] `PurchaseOrderService.start_return()` — L883
- [ ] `PurchaseOrderService.complete_return()` — L937
- [ ] `PurchaseOrderService.void_return()` — L1004
- [ ] `PurchaseOrderService.list_returns()` — L1044
- [ ] `PurchaseOrderService.get_return()` — L1048
- [ ] `PurchaseOrderService.list_active_orders_for_context()` — L1052
- [ ] `PurchaseOrderService.delete_purchase_order()` — L1184
- [ ] `PurchaseOrderService.add_item()` — L1193
- [ ] `PurchaseOrderService.update_item()` — L1218
- [ ] `PurchaseOrderService.remove_item()` — L1243
- [ ] `PurchaseOrderService.sync_items()` — L1266
- [ ] `PurchaseOrderService.get_items()` — L1308
- [ ] `PurchaseOrderService.list_events()` — L1312
- [ ] `PurchaseOrderService.list_approvers()` — L1316
- [ ] `PurchaseOrderService.approval_summary_for()` — L1319
- [ ] `PurchaseOrderService.add_approver()` — L1323
- [ ] `PurchaseOrderService.remove_approver()` — L1346
- [ ] `PurchaseOrderService.set_approval()` — L1358
- [ ] `PurchaseOrderService.void_purchase_order()` — L1370
- [ ] `PurchaseOrderService.create_invoice_for_purchase_order()` — L1452

### DAOs

#### `app/dao/purchase_order.py` (19)

#### class `PurchaseOrderDAO` (BaseDAO[PurchaseOrder, PurchaseOrderCreate, PurchaseOrderUpdate])

- [ ] `PurchaseOrderDAO.get_by_workspace()` — L134
- [ ] `PurchaseOrderDAO.list_for_hub()` — L155
- [ ] `PurchaseOrderDAO.count_for_hub()` — L172
- [ ] `PurchaseOrderDAO.list_recent_for_hub()` — L181
- [ ] `PurchaseOrderDAO.get_pending_highlights_for_hub()` — L196
- [ ] `PurchaseOrderDAO.aggregate_hub_stats()` — L243
- [ ] `PurchaseOrderDAO.list_for_destination()` — L284
- [ ] `PurchaseOrderDAO.get_by_id_and_workspace()` — L304
- [ ] `PurchaseOrderDAO.get_by_invoice_id()` — L312
- [ ] `PurchaseOrderDAO.get_next_number()` — L324
- [ ] `PurchaseOrderDAO.allocate_po_number()` — L328

#### class `PurchaseOrderItemDAO` (BaseDAO[PurchaseOrderItem, PurchaseOrderItemCreate, PurchaseOrderItemUpdate])

- [ ] `PurchaseOrderItemDAO.get_by_order()` — L372
- [ ] `PurchaseOrderItemDAO.get_by_purchase_order_ids()` — L375
- [ ] `PurchaseOrderItemDAO.get_by_id_and_workspace()` — L394
- [ ] `PurchaseOrderItemDAO.summarize_by_purchase_order_ids()` — L397
- [ ] `PurchaseOrderItemDAO.preview_names_by_purchase_order_ids()` — L429

#### module-level functions

- [ ] `_purchase_order_is_fully_closed_clause()` — L23 _(private)_
- [ ] `_apply_purchase_order_hub_filters()` — L28 _(private)_
- [ ] `_hub_base_query()` — L123 _(private)_

#### `app/dao/purchase_order_approver.py` (2)

#### class `PurchaseOrderApproverDAO` (BaseDAO[PurchaseOrderApprover, PurchaseOrderApproverCreate, PurchaseOrderApproverCreate])

- [ ] `PurchaseOrderApproverDAO.get_by_order()` — L10
- [ ] `PurchaseOrderApproverDAO.get_by_order_and_user()` — L23

#### `app/dao/purchase_order_event.py` (1)

#### class `PurchaseOrderEventDAO` (BaseDAO[PurchaseOrderEvent, PurchaseOrderEventResponse, PurchaseOrderEventResponse])

- [ ] `PurchaseOrderEventDAO.get_by_order()` — L11

#### `app/dao/purchase_order_return.py` (6)

#### class `DAOPurchaseOrderReturn` (BaseDAO[PurchaseOrderReturn, PurchaseOrderReturnCreate, PurchaseOrderReturnCreate])

- [ ] `DAOPurchaseOrderReturn.generate_return_number()` — L13
- [ ] `DAOPurchaseOrderReturn.create_with_user()` — L26
- [ ] `DAOPurchaseOrderReturn.get_by_purchase_order()` — L47
- [ ] `DAOPurchaseOrderReturn.get_open_by_purchase_order()` — L60
- [ ] `DAOPurchaseOrderReturn.get_by_invoice_id()` — L73

#### class `DAOPurchaseOrderReturnItem` (BaseDAO[PurchaseOrderReturnItem, PurchaseOrderReturnCreate, PurchaseOrderReturnCreate])

- [ ] `DAOPurchaseOrderReturnItem.get_by_return()` — L89

## Sales Orders & Deliveries (100 callables)

### Managers

#### `app/managers/sales_manager.py` (29)

#### class `SalesManager` (BaseManager[SalesOrder])

- [ ] `SalesManager.__init__()` — L83 _(dunder)_
- [ ] `SalesManager.create_sales_order_with_items()` — L92
- [ ] `SalesManager.create_delivery_with_items()` — L171
- [ ] `SalesManager.complete_delivery()` — L273
- [ ] `SalesManager.cancel_delivery()` — L370
- [ ] `SalesManager.update_delivery()` — L408
- [ ] `SalesManager.fulfill_service_item()` — L452
- [ ] `SalesManager._recompute_is_fully_delivered()` — L506 _(private)_
- [ ] `SalesManager._base_sections_confirmed()` — L523 _(private)_
- [ ] `SalesManager.is_so_financially_locked()` — L526
- [ ] `SalesManager.unlink_invoice_from_so()` — L537
- [ ] `SalesManager.set_section_confirm()` — L556
- [ ] `SalesManager.reset_approvals()` — L610
- [ ] `SalesManager.apply_post_invoice_confirms()` — L628
- [ ] `SalesManager.mark_order_complete()` — L647
- [ ] `SalesManager.reopen_for_return()` — L684
- [ ] `SalesManager._invoice_payment_status()` — L707 _(private)_
- [ ] `SalesManager.sync_so_for_linked_invoice()` — L713
- [ ] `SalesManager.sync_so_paid()` — L720
- [ ] `SalesManager.list_approvers()` — L741
- [ ] `SalesManager.approval_summary()` — L756
- [ ] `SalesManager.approvals_met()` — L768
- [ ] `SalesManager.add_approver()` — L771
- [ ] `SalesManager.remove_approver()` — L797
- [ ] `SalesManager.set_approval()` — L813
- [ ] `SalesManager.log_event()` — L844
- [ ] `SalesManager.list_events()` — L861

#### module-level functions

- [ ] `all_deliverable_items_delivered()` — L39
- [ ] `all_fulfilment_items_fulfilled()` — L52

#### `app/managers/sales_order_return_manager.py` (6)

#### class `SalesOrderReturnManager` (BaseManager[SalesOrderReturn])

- [ ] `SalesOrderReturnManager.__init__()` — L17 _(dunder)_
- [ ] `SalesOrderReturnManager.has_open_return()` — L23
- [ ] `SalesOrderReturnManager.validate_and_build_items()` — L28
- [ ] `SalesOrderReturnManager.get_return()` — L70
- [ ] `SalesOrderReturnManager.list_returns()` — L80
- [ ] `SalesOrderReturnManager.sync_return_paid()` — L87

### Services

#### `app/services/sales_service.py` (36)

#### class `SalesService` (BaseService)

- [ ] `SalesService.__init__()` — L41 _(dunder)_
- [ ] `SalesService._attach_receivable_invoice_to_sales_order()` — L46 _(private)_
- [ ] `SalesService._delete_linked_draft_invoice_for_so()` — L133 _(private)_
- [ ] `SalesService._sync_draft_invoice_for_so()` — L156 _(private)_
- [ ] `SalesService.create_invoice_for_sales_order()` — L187
- [ ] `SalesService.finalize_sales_order_invoice()` — L221
- [x] `SalesService.create_sales_order()` — L278 ~~[DELETED DEAD CODE]~~
- [ ] `SalesService.create_sales_order_from_dict()` — L305
- [ ] `SalesService.get_sales_order()` — L349
- [ ] `SalesService.get_sales_orders()` — L377
- [ ] `SalesService._attach_invoice_payment_status()` — L403 _(private)_
- [ ] `SalesService.update_sales_order()` — L418
- [ ] `SalesService.create_delivery()` — L462
- [ ] `SalesService.complete_delivery()` — L512
- [ ] `SalesService.cancel_delivery()` — L609
- [ ] `SalesService.update_delivery()` — L646
- [ ] `SalesService.fulfill_service_item()` — L683
- [ ] `SalesService.get_deliveries_for_order()` — L743
- [ ] `SalesService.get_sales_order_items()` — L764
- [ ] `SalesService.get_delivery()` — L786
- [ ] `SalesService.get_deliveries()` — L813
- [ ] `SalesService.get_delivery_items()` — L843
- [ ] `SalesService._attach_return_invoice_for_so()` — L867 _(private)_
- [ ] `SalesService.start_return()` — L921
- [ ] `SalesService.complete_return()` — L972
- [ ] `SalesService.void_return()` — L1052
- [ ] `SalesService.list_returns()` — L1092
- [ ] `SalesService.get_return()` — L1096
- [ ] `SalesService.mark_order_complete()` — L1102
- [ ] `SalesService.set_section_confirm()` — L1119
- [ ] `SalesService.list_approvers()` — L1138
- [ ] `SalesService.approval_summary()` — L1143
- [ ] `SalesService.add_approver()` — L1146
- [ ] `SalesService.remove_approver()` — L1158
- [ ] `SalesService.set_approval()` — L1168
- [ ] `SalesService.list_events()` — L1182

### DAOs

#### `app/dao/sales_delivery.py` (6)

#### class `DAOSalesDelivery` (BaseDAO[SalesDelivery, SalesDeliveryCreate, SalesDeliveryUpdate])

- [ ] `DAOSalesDelivery.generate_delivery_number()` — L13
- [ ] `DAOSalesDelivery.create_with_user()` — L40
- [ ] `DAOSalesDelivery.get_by_sales_order()` — L77
- [ ] `DAOSalesDelivery.get_by_status()` — L94
- [ ] `DAOSalesDelivery.get_by_date_range()` — L115
- [x] `DAOSalesDelivery.get_pending_deliveries()` — L138 ~~[DELETED DEAD CODE]~~

#### `app/dao/sales_delivery_item.py` (3)

#### class `DAOSalesDeliveryItem` (BaseDAO[SalesDeliveryItem, SalesDeliveryItemCreate, SalesDeliveryItemUpdate])

- [ ] `DAOSalesDeliveryItem.get_by_delivery()` — L12
- [x] `DAOSalesDeliveryItem.get_by_sales_order_item()` — L29 ~~[DELETED DEAD CODE]~~
- [x] `DAOSalesDeliveryItem.calculate_total_delivered()` — L46 ~~[DELETED DEAD CODE]~~

#### `app/dao/sales_order.py` (8)

#### class `DAOSalesOrder` (BaseDAO[SalesOrder, SalesOrderCreate, SalesOrderUpdate])

- [ ] `DAOSalesOrder.get_by_invoice_id()` — L13
- [ ] `DAOSalesOrder.generate_sales_order_number()` — L25
- [ ] `DAOSalesOrder.create_with_user()` — L53
- [x] `DAOSalesOrder.get_by_account()` — L90 ~~[DELETED DEAD CODE]~~
- [ ] `DAOSalesOrder.get_by_factory()` — L111
- [ ] `DAOSalesOrder.get_by_status()` — L132
- [x] `DAOSalesOrder.get_pending_deliveries()` — L153 ~~[DELETED DEAD CODE]~~
- [x] `DAOSalesOrder.get_uninvoiced_orders()` — L168 ~~[DELETED DEAD CODE]~~

#### `app/dao/sales_order_approver.py` (2)

#### class `SalesOrderApproverDAO` (BaseDAO[SalesOrderApprover, SalesOrderApproverCreate, SalesOrderApproverCreate])

- [ ] `SalesOrderApproverDAO.get_by_order()` — L10
- [ ] `SalesOrderApproverDAO.get_by_order_and_user()` — L23

#### `app/dao/sales_order_event.py` (1)

#### class `SalesOrderEventDAO` (BaseDAO[SalesOrderEvent, SalesOrderEventResponse, SalesOrderEventResponse])

- [ ] `SalesOrderEventDAO.get_by_order()` — L11

#### `app/dao/sales_order_item.py` (3)

#### class `DAOSalesOrderItem` (BaseDAO[SalesOrderItem, SalesOrderItemCreate, SalesOrderItemUpdate])

- [ ] `DAOSalesOrderItem.get_by_sales_order()` — L12
- [ ] `DAOSalesOrderItem.get_by_item()` — L29
- [x] `DAOSalesOrderItem.get_pending_items()` — L50 ~~[DELETED DEAD CODE]~~

#### `app/dao/sales_order_return.py` (6)

#### class `DAOSalesOrderReturn` (BaseDAO[SalesOrderReturn, SalesOrderReturnCreate, SalesOrderReturnCreate])

- [ ] `DAOSalesOrderReturn.generate_return_number()` — L13
- [ ] `DAOSalesOrderReturn.create_with_user()` — L26
- [ ] `DAOSalesOrderReturn.get_by_sales_order()` — L47
- [ ] `DAOSalesOrderReturn.get_open_by_sales_order()` — L60
- [ ] `DAOSalesOrderReturn.get_by_invoice_id()` — L73

#### class `DAOSalesOrderReturnItem` (BaseDAO[SalesOrderReturnItem, SalesOrderReturnCreate, SalesOrderReturnCreate])

- [ ] `DAOSalesOrderReturnItem.get_by_return()` — L89

## Transfer Orders (85 callables)

### Managers

#### `app/managers/transfer_order_manager.py` (41)

#### class `TransferOrderManager` (BaseManager[TransferOrder])

- [ ] `TransferOrderManager.__init__()` — L56 _(dunder)_
- [ ] `TransferOrderManager._is_completed()` — L64 _(private)_
- [ ] `TransferOrderManager._route_defined()` — L67 _(private)_
- [ ] `TransferOrderManager._route_valid()` — L75 _(private)_
- [ ] `TransferOrderManager._order_items()` — L83 _(private)_
- [ ] `TransferOrderManager._ready_for_approval()` — L90 _(private)_
- [ ] `TransferOrderManager._validate_ready_for_approval()` — L97 _(private)_
- [ ] `TransferOrderManager._has_any_approval()` — L119 _(private)_
- [x] `TransferOrderManager._all_items_transferred()` — L125 _(private)_ ~~[DELETED DEAD CODE]~~
- [ ] `TransferOrderManager._format_scalar_value()` — L130 _(private)_
- [ ] `TransferOrderManager._format_location_id()` — L140 _(private)_
- [ ] `TransferOrderManager._format_field_value()` — L163 _(private)_
- [ ] `TransferOrderManager._collect_field_changes()` — L185 _(private)_
- [ ] `TransferOrderManager._log_field_change_event()` — L218 _(private)_
- [ ] `TransferOrderManager._guard_confirmed_updates()` — L235 _(private)_
- [ ] `TransferOrderManager._guard_item_mutations()` — L255 _(private)_
- [ ] `TransferOrderManager.create_transfer_order()` — L268
- [ ] `TransferOrderManager.update_transfer_order()` — L319
- [ ] `TransferOrderManager.get_transfer_order()` — L344
- [ ] `TransferOrderManager.list_transfer_orders()` — L353
- [ ] `TransferOrderManager.list_transfer_orders_for_hub()` — L362
- [ ] `TransferOrderManager.count_transfer_orders_for_hub()` — L379
- [ ] `TransferOrderManager.transfer_order_hub_stats()` — L384
- [ ] `TransferOrderManager.list_transfer_orders_recent_for_hub()` — L387
- [ ] `TransferOrderManager.count_transfer_orders_machine_involved_for_hub()` — L394
- [ ] `TransferOrderManager.transfer_order_pending_highlights_for_hub()` — L401
- [ ] `TransferOrderManager.delete_transfer_order()` — L408
- [ ] `TransferOrderManager.mark_order_complete()` — L430
- [ ] `TransferOrderManager._ensure_catalog_item_not_on_to()` — L488 _(private)_
- [ ] `TransferOrderManager.add_item()` — L510
- [ ] `TransferOrderManager.update_item()` — L534
- [ ] `TransferOrderManager.remove_item()` — L584
- [ ] `TransferOrderManager.get_items()` — L601
- [ ] `TransferOrderManager.list_approvers()` — L606
- [ ] `TransferOrderManager.approval_summary()` — L622
- [ ] `TransferOrderManager.approvals_met()` — L635
- [ ] `TransferOrderManager.add_approver()` — L638
- [ ] `TransferOrderManager.remove_approver()` — L677
- [ ] `TransferOrderManager.set_approval()` — L697
- [ ] `TransferOrderManager.log_event()` — L723
- [ ] `TransferOrderManager.list_events()` — L740

### Services

#### `app/services/transfer_order_service.py` (20)

#### class `TransferOrderService` (BaseService)

- [ ] `TransferOrderService.__init__()` — L23 _(dunder)_
- [ ] `TransferOrderService.create_transfer_order()` — L27
- [ ] `TransferOrderService.update_transfer_order()` — L40
- [ ] `TransferOrderService.get_transfer_order()` — L67
- [ ] `TransferOrderService.list_transfer_orders()` — L70
- [ ] `TransferOrderService._hub_filter_kwargs()` — L79 _(private)_
- [ ] `TransferOrderService.list_transfer_orders_page()` — L106
- [ ] `TransferOrderService.get_transfer_order_hub_stats()` — L146
- [ ] `TransferOrderService.delete_transfer_order()` — L211
- [ ] `TransferOrderService.mark_order_complete()` — L219
- [ ] `TransferOrderService.add_item()` — L234
- [ ] `TransferOrderService.update_item()` — L262
- [ ] `TransferOrderService.remove_item()` — L275
- [ ] `TransferOrderService.get_items()` — L284
- [ ] `TransferOrderService.list_events()` — L288
- [ ] `TransferOrderService.list_approvers()` — L292
- [ ] `TransferOrderService.approval_summary_for()` — L295
- [ ] `TransferOrderService.add_approver()` — L299
- [ ] `TransferOrderService.remove_approver()` — L322
- [ ] `TransferOrderService.set_approval()` — L334

### DAOs

#### `app/dao/transfer_order.py` (21)

#### class `TransferOrderDAO` (BaseDAO[TransferOrder, TransferOrderCreate, TransferOrderUpdate])

- [ ] `TransferOrderDAO.get_by_workspace()` — L195
- [ ] `TransferOrderDAO.list_for_hub()` — L205
- [ ] `TransferOrderDAO.count_for_hub()` — L222
- [ ] `TransferOrderDAO.list_recent_for_hub()` — L231
- [ ] `TransferOrderDAO.count_machine_involved_for_hub()` — L246
- [ ] `TransferOrderDAO.get_pending_highlights_for_hub()` — L267
- [ ] `TransferOrderDAO.aggregate_hub_stats()` — L307
- [ ] `TransferOrderDAO.list_touching_location_incomplete()` — L335
- [ ] `TransferOrderDAO.list_inbound_to_storage_incomplete()` — L365
- [ ] `TransferOrderDAO.get_by_id_and_workspace()` — L386
- [ ] `TransferOrderDAO.get_next_number()` — L396

#### class `TransferOrderItemDAO` (BaseDAO[TransferOrderItem, TransferOrderItemCreate, TransferOrderItemUpdate])

- [ ] `TransferOrderItemDAO.get_by_order()` — L421
- [ ] `TransferOrderItemDAO.get_by_transfer_order_ids()` — L434
- [ ] `TransferOrderItemDAO.get_by_id_and_workspace()` — L453

#### module-level functions

- [ ] `_transfer_order_is_complete_clause()` — L23 _(private)_
- [ ] `_location_factory_match()` — L27 _(private)_
- [ ] `_location_resolvable_clause()` — L57 _(private)_
- [ ] `_apply_transfer_factory_filter()` — L61 _(private)_
- [ ] `_apply_transfer_order_hub_filters()` — L87 _(private)_
- [ ] `_transfer_route_defined_clause()` — L178 _(private)_
- [ ] `_hub_base_query()` — L189 _(private)_

#### `app/dao/transfer_order_approver.py` (2)

#### class `TransferOrderApproverDAO` (BaseDAO[TransferOrderApprover, TransferOrderApproverCreate, TransferOrderApproverCreate])

- [ ] `TransferOrderApproverDAO.get_by_order()` — L10
- [ ] `TransferOrderApproverDAO.get_by_order_and_user()` — L23

#### `app/dao/transfer_order_event.py` (1)

#### class `TransferOrderEventDAO` (BaseDAO[TransferOrderEvent, object, object])

- [ ] `TransferOrderEventDAO.get_by_order()` — L10

## Work Orders (187 callables)

### Managers

#### `app/managers/work_order_manager.py` (58)

#### class `WorkOrderManager` (BaseManager[WorkOrder])

- [ ] `WorkOrderManager.__init__()` — L74 _(dunder)_
- [ ] `WorkOrderManager._is_locked()` — L82 _(private)_
- [ ] `WorkOrderManager._has_recorded_approvals()` — L85 _(private)_
- [ ] `WorkOrderManager.is_approvable()` — L89
- [ ] `WorkOrderManager.approvability_gap_reason()` — L92
- [ ] `WorkOrderManager._format_scalar_value()` — L99 _(private)_
- [ ] `WorkOrderManager._variance_vs_planned()` — L111 _(private)_
- [ ] `WorkOrderManager._schedule_metadata_for_actual()` — L131 _(private)_
- [ ] `WorkOrderManager._started_worker_metadata()` — L142 _(private)_
- [ ] `WorkOrderManager._collect_field_changes()` — L154 _(private)_
- [ ] `WorkOrderManager._work_order_type_name()` — L177 _(private)_
- [ ] `WorkOrderManager.resolve_invoice_account_id()` — L183
- [ ] `WorkOrderManager._derive_default_title()` — L191 _(private)_
- [ ] `WorkOrderManager.create_work_order()` — L226
- [ ] `WorkOrderManager.create_work_order_from_template()` — L299
- [ ] `WorkOrderManager.update_work_order()` — L367
- [ ] `WorkOrderManager.get_work_order()` — L496
- [ ] `WorkOrderManager.list_work_orders()` — L502
- [ ] `WorkOrderManager.bulk_delete_future_recurrence_drafts()` — L523
- [ ] `WorkOrderManager.delete_work_order()` — L548
- [ ] `WorkOrderManager.list_approvers()` — L565
- [ ] `WorkOrderManager.approval_summary()` — L579
- [ ] `WorkOrderManager.approvals_met()` — L588
- [ ] `WorkOrderManager.reset_approvals()` — L591
- [ ] `WorkOrderManager._recompute_approval_status()` — L609 _(private)_
- [ ] `WorkOrderManager.add_approver()` — L639
- [ ] `WorkOrderManager.remove_approver()` — L668
- [ ] `WorkOrderManager.set_approval()` — L688
- [ ] `WorkOrderManager._consume_item()` — L714 _(private)_
- [ ] `WorkOrderManager._reverse_item_consumption()` — L766 _(private)_
- [ ] `WorkOrderManager._adjust_consumed_item_quantity()` — L793 _(private)_
- [ ] `WorkOrderManager._apply_item_completion()` — L891 _(private)_
- [ ] `WorkOrderManager._set_machine_status()` — L972 _(private)_
- [ ] `WorkOrderManager._previous_machine_status()` — L998 _(private)_
- [ ] `WorkOrderManager.start_work_order()` — L1005
- [ ] `WorkOrderManager._planned_date_noon_utc()` — L1046 _(private)_
- [ ] `WorkOrderManager._run_start_side_effects()` — L1049 _(private)_
- [ ] `WorkOrderManager._ensure_active_workspace_member()` — L1066 _(private)_
- [ ] `WorkOrderManager._sync_assignees_from_text()` — L1078 _(private)_
- [ ] `WorkOrderManager._resolve_completion_workers()` — L1091 _(private)_
- [ ] `WorkOrderManager.complete_as_planned()` — L1128
- [ ] `WorkOrderManager.finalize_completion()` — L1201
- [ ] `WorkOrderManager.void_work_order()` — L1293
- [ ] `WorkOrderManager._ensure_catalog_item_not_on_wo()` — L1329 _(private)_
- [ ] `WorkOrderManager._guard_item_mutations()` — L1342 _(private)_
- [ ] `WorkOrderManager.add_item()` — L1348
- [ ] `WorkOrderManager.update_item()` — L1388
- [ ] `WorkOrderManager.remove_item()` — L1445
- [ ] `WorkOrderManager.get_items()` — L1477
- [ ] `WorkOrderManager._apply_sheet_entry_lines()` — L1482 _(private)_
- [ ] `WorkOrderManager.sheet_entry()` — L1529
- [ ] `WorkOrderManager.sync_recurrence_drafts_for_machine()` — L1607
- [ ] `WorkOrderManager._maybe_seed_template_recurrence()` — L1638 _(private)_
- [ ] `WorkOrderManager.list_sheet_orders()` — L1697
- [ ] `WorkOrderManager.count_sheet_orders()` — L1729
- [ ] `WorkOrderManager.sheet_daily_counts()` — L1759
- [ ] `WorkOrderManager.log_event()` — L1785
- [ ] `WorkOrderManager.list_events()` — L1799

#### `app/managers/work_order_template_manager.py` (15)

#### class `WorkOrderTemplateManager` (BaseManager[WorkOrderTemplate])

- [ ] `WorkOrderTemplateManager.__init__()` — L25 _(dunder)_
- [ ] `WorkOrderTemplateManager._replace_approvers()` — L31 _(private)_
- [ ] `WorkOrderTemplateManager.create_template()` — L44
- [ ] `WorkOrderTemplateManager.update_template()` — L73
- [ ] `WorkOrderTemplateManager.get_template()` — L97
- [ ] `WorkOrderTemplateManager.list_templates()` — L103
- [ ] `WorkOrderTemplateManager.delete_template()` — L115
- [ ] `WorkOrderTemplateManager.restore_template()` — L123
- [ ] `WorkOrderTemplateManager.add_item()` — L130
- [ ] `WorkOrderTemplateManager.update_item()` — L144
- [ ] `WorkOrderTemplateManager.remove_item()` — L153
- [ ] `WorkOrderTemplateManager.get_items()` — L161
- [ ] `WorkOrderTemplateManager.get_approvers()` — L164
- [ ] `WorkOrderTemplateManager.generate_drafts_for_anchored_range()` — L167
- [ ] `WorkOrderTemplateManager.generate_drafts()` — L220

#### `app/managers/work_order_type_manager.py` (7)

#### class `WorkOrderTypeManager` (BaseManager[WorkOrderType])

- [ ] `WorkOrderTypeManager.__init__()` — L23 _(dunder)_
- [ ] `WorkOrderTypeManager.create_work_order_type()` — L27
- [ ] `WorkOrderTypeManager.update_work_order_type()` — L50
- [ ] `WorkOrderTypeManager.get_work_order_type()` — L87
- [ ] `WorkOrderTypeManager.search_work_order_types()` — L101
- [ ] `WorkOrderTypeManager.delete_work_order_type()` — L121
- [ ] `WorkOrderTypeManager._check_name_exists()` — L142 _(private)_

### Services

#### `app/services/machine_work_service.py` (7)

#### class `MachineWorkService` (BaseService)

- [ ] `MachineWorkService.collect_raw_items()` — L34
- [ ] `MachineWorkService.upcoming_work()` — L69
- [ ] `MachineWorkService.dates_by_machine()` — L141
- [ ] `MachineWorkService.earliest_upcoming_on_or_after()` — L176
- [ ] `MachineWorkService.has_overdue()` — L181
- [ ] `MachineWorkService.has_upcoming_in_horizon()` — L185
- [x] `MachineWorkService.has_upcoming_work()` — L189 ~~[DELETED DEAD CODE]~~

#### `app/services/work_order_service.py` (30)

#### class `_WorkOrderEnrichment`

_(no methods defined in class body)_


#### class `WorkOrderService` (BaseService)

- [ ] `WorkOrderService.__init__()` — L47 _(dunder)_
- [ ] `WorkOrderService._load_work_order_enrichment()` — L52 _(private)_
- [ ] `WorkOrderService._to_work_order_response()` — L94 _(private)_
- [ ] `WorkOrderService._to_work_order_responses()` — L117 _(private)_
- [ ] `WorkOrderService.create_work_order()` — L128
- [ ] `WorkOrderService.create_work_order_from_template()` — L141
- [ ] `WorkOrderService.update_work_order()` — L156
- [ ] `WorkOrderService.get_work_order()` — L175
- [ ] `WorkOrderService.list_work_orders()` — L178
- [ ] `WorkOrderService.bulk_delete_future_recurrence_drafts()` — L199
- [ ] `WorkOrderService.sheet_entry()` — L227
- [ ] `WorkOrderService.list_sheet_bundles()` — L240
- [ ] `WorkOrderService.sheet_daily_counts()` — L322
- [ ] `WorkOrderService.delete_work_order()` — L347
- [ ] `WorkOrderService.start_work_order()` — L358
- [ ] `WorkOrderService.complete_work_order()` — L368
- [ ] `WorkOrderService.complete_work_order_as_planned()` — L418
- [ ] `WorkOrderService.void_work_order()` — L466
- [ ] `WorkOrderService.create_invoice_for_work_order()` — L491
- [ ] `WorkOrderService.list_approvers()` — L561
- [ ] `WorkOrderService.approval_summary_for()` — L566
- [ ] `WorkOrderService.add_approver()` — L570
- [ ] `WorkOrderService.remove_approver()` — L591
- [ ] `WorkOrderService.approve_as_me()` — L599
- [ ] `WorkOrderService.unapprove_as_me()` — L609
- [ ] `WorkOrderService.list_events()` — L620
- [ ] `WorkOrderService.add_item()` — L624
- [ ] `WorkOrderService.update_item()` — L634
- [ ] `WorkOrderService.remove_item()` — L644
- [ ] `WorkOrderService.get_items()` — L653

#### `app/services/work_order_template_service.py` (13)

#### class `WorkOrderTemplateService` (BaseService)

- [ ] `WorkOrderTemplateService.__init__()` — L21 _(dunder)_
- [ ] `WorkOrderTemplateService.create_template()` — L25
- [ ] `WorkOrderTemplateService.update_template()` — L38
- [ ] `WorkOrderTemplateService.get_template()` — L51
- [ ] `WorkOrderTemplateService.list_templates()` — L54
- [ ] `WorkOrderTemplateService.delete_template()` — L66
- [ ] `WorkOrderTemplateService.restore_template()` — L74
- [ ] `WorkOrderTemplateService.add_item()` — L85
- [ ] `WorkOrderTemplateService.update_item()` — L97
- [ ] `WorkOrderTemplateService.remove_item()` — L109
- [ ] `WorkOrderTemplateService.get_items()` — L118
- [ ] `WorkOrderTemplateService.get_approvers()` — L121
- [ ] `WorkOrderTemplateService.generate_drafts()` — L124

#### `app/services/work_order_type_service.py` (6)

#### class `WorkOrderTypeService` (BaseService)

- [ ] `WorkOrderTypeService.__init__()` — L14 _(dunder)_
- [ ] `WorkOrderTypeService.create_work_order_type()` — L18
- [ ] `WorkOrderTypeService.get_work_order_type()` — L32
- [ ] `WorkOrderTypeService.get_work_order_types()` — L35
- [ ] `WorkOrderTypeService.update_work_order_type()` — L43
- [ ] `WorkOrderTypeService.delete_work_order_type()` — L57

### Utils

#### `app/utils/work_order_calendar.py` (1)

#### module-level functions

- [ ] `work_order_calendar_date()` — L5

#### `app/utils/work_order_generation.py` (1)

#### module-level functions

- [ ] `resolve_template_machine_ids()` — L12

#### `app/utils/work_order_recurrence.py` (7)

#### module-level functions

- [ ] `validate_recurrence_span()` — L13
- [ ] `advance_next_generation_date()` — L21
- [ ] `_apply_recurrence_range()` — L53 _(private)_
- [ ] `seed_recurrence_from_planned_date()` — L72
- [ ] `reseed_recurrence_program()` — L83
- [ ] `is_recurrence_program_active()` — L94
- [ ] `should_advance_template()` — L103

#### `app/utils/work_order_workers.py` (7)

#### class `MemberLookup`

_(no methods defined in class body)_


#### class `WorkerNameResolution`

_(no methods defined in class body)_


#### module-level functions

- [ ] `parse_worker_names()` — L17
- [ ] `join_worker_names()` — L23
- [ ] `_normalize()` — L41 _(private)_
- [ ] `resolve_names_to_members()` — L45
- [ ] `resolve_worker_text_to_members()` — L79
- [ ] `load_active_member_lookups()` — L86
- [ ] `display_names_for_user_ids()` — L101

### DAOs

#### `app/dao/work_order.py` (14)

#### class `WorkOrderDAO` (BaseDAO[WorkOrder, WorkOrderCreate, WorkOrderUpdate])

- [ ] `WorkOrderDAO.get_by_workspace()` — L111
- [ ] `WorkOrderDAO.list_future_drafts_for_template_machine()` — L148
- [ ] `WorkOrderDAO.list_drafts_outside_range_for_template_machine()` — L173
- [ ] `WorkOrderDAO.get_by_machine_date_type()` — L202
- [ ] `WorkOrderDAO.list_for_sheet()` — L226
- [ ] `WorkOrderDAO.count_for_sheet()` — L265
- [ ] `WorkOrderDAO.count_by_calendar_date_for_sheet()` — L297
- [ ] `WorkOrderDAO.get_by_id_and_workspace()` — L334
- [ ] `WorkOrderDAO.get_next_number()` — L343
- [ ] `WorkOrderDAO.soft_delete()` — L360
- [ ] `WorkOrderDAO.restore()` — L371

#### module-level functions

- [ ] `_work_order_calendar_date_expr()` — L15 _(private)_
- [ ] `_apply_sheet_list_filters()` — L20 _(private)_
- [ ] `_sheet_base_query()` — L70 _(private)_

#### `app/dao/work_order_approver.py` (2)

#### class `WorkOrderApproverDAO` (BaseDAO[WorkOrderApprover, WorkOrderApproverCreate, WorkOrderApproverCreate])

- [ ] `WorkOrderApproverDAO.get_by_order()` — L10
- [ ] `WorkOrderApproverDAO.get_by_order_and_user()` — L23

#### `app/dao/work_order_assignee.py` (3)

#### class `WorkOrderAssigneeDAO` (BaseDAO[WorkOrderAssignee, object, object])

- [ ] `WorkOrderAssigneeDAO.get_user_ids_by_orders()` — L11
- [ ] `WorkOrderAssigneeDAO.get_user_ids_by_order()` — L34
- [ ] `WorkOrderAssigneeDAO.replace_for_order()` — L48

#### `app/dao/work_order_completer.py` (3)

#### class `WorkOrderCompleterDAO` (BaseDAO[WorkOrderCompleter, object, object])

- [ ] `WorkOrderCompleterDAO.get_user_ids_by_orders()` — L11
- [ ] `WorkOrderCompleterDAO.get_user_ids_by_order()` — L34
- [ ] `WorkOrderCompleterDAO.replace_for_order()` — L48

#### `app/dao/work_order_event.py` (1)

#### class `WorkOrderEventDAO` (BaseDAO[WorkOrderEvent, object, object])

- [ ] `WorkOrderEventDAO.get_by_order()` — L10

#### `app/dao/work_order_item.py` (2)

#### class `WorkOrderItemDAO` (BaseDAO[WorkOrderItem, WorkOrderItemCreate, WorkOrderItemUpdate])

- [ ] `WorkOrderItemDAO.get_by_work_order()` — L15
- [ ] `WorkOrderItemDAO.get_by_id_and_workspace()` — L32

#### `app/dao/work_order_template.py` (7)

#### class `WorkOrderTemplateDAO` (BaseDAO[WorkOrderTemplate, WorkOrderTemplateCreate, WorkOrderTemplateUpdate])

- [ ] `WorkOrderTemplateDAO.get_by_workspace()` — L18
- [ ] `WorkOrderTemplateDAO.list_recurring_due()` — L31
- [ ] `WorkOrderTemplateDAO.get_by_id_and_workspace()` — L60

#### class `WorkOrderTemplateItemDAO` (BaseDAO[WorkOrderTemplateItem, WorkOrderTemplateItemCreate, WorkOrderTemplateItemUpdate])

- [ ] `WorkOrderTemplateItemDAO.get_by_template()` — L67
- [ ] `WorkOrderTemplateItemDAO.get_by_id_and_workspace()` — L73

#### class `WorkOrderTemplateApproverDAO` (BaseDAO[WorkOrderTemplateApprover, WorkOrderTemplateApproverCreate, WorkOrderTemplateApproverCreate])

- [ ] `WorkOrderTemplateApproverDAO.get_by_template()` — L80
- [ ] `WorkOrderTemplateApproverDAO.delete_all_for_template()` — L86

#### `app/dao/work_order_type.py` (3)

#### class `DAOWorkOrderType` (BaseDAO[WorkOrderType, WorkOrderTypeCreate, WorkOrderTypeUpdate])

- [x] `DAOWorkOrderType.get_active_types()` — L25 ~~[DELETED DEAD CODE]~~
- [ ] `DAOWorkOrderType.soft_delete()` — L42
- [ ] `DAOWorkOrderType.restore()` — L53

## Expense Orders (88 callables)

### Managers

#### `app/managers/expense_order_manager.py` (37)

#### class `ExpenseOrderManager` (BaseManager[ExpenseOrder])

- [ ] `ExpenseOrderManager.__init__()` — L49 _(dunder)_
- [ ] `ExpenseOrderManager._is_completed()` — L57 _(private)_
- [ ] `ExpenseOrderManager._has_recorded_approvals()` — L60 _(private)_
- [ ] `ExpenseOrderManager.is_approvable()` — L66
- [ ] `ExpenseOrderManager.approvability_gap_reason()` — L82
- [ ] `ExpenseOrderManager._validate_order_allocation()` — L94 _(private)_
- [ ] `ExpenseOrderManager.resolve_invoice_account_id()` — L119
- [ ] `ExpenseOrderManager.reset_approvals()` — L127
- [ ] `ExpenseOrderManager._format_scalar_value()` — L152 _(private)_
- [ ] `ExpenseOrderManager._collect_field_changes()` — L162 _(private)_
- [ ] `ExpenseOrderManager._guard_confirmed_updates()` — L183 _(private)_
- [ ] `ExpenseOrderManager._guard_item_mutations()` — L190 _(private)_
- [ ] `ExpenseOrderManager._prepare_item_dict()` — L197 _(private)_
- [ ] `ExpenseOrderManager.create_expense_order()` — L204
- [ ] `ExpenseOrderManager.update_expense_order()` — L247
- [ ] `ExpenseOrderManager.get_expense_order()` — L281
- [ ] `ExpenseOrderManager.list_expense_orders()` — L287
- [ ] `ExpenseOrderManager.list_expense_orders_for_hub()` — L301
- [ ] `ExpenseOrderManager.count_expense_orders_for_hub()` — L318
- [ ] `ExpenseOrderManager.expense_order_hub_stats()` — L323
- [ ] `ExpenseOrderManager.list_expense_orders_recent_for_hub()` — L326
- [ ] `ExpenseOrderManager.expense_order_financial_snapshot()` — L333
- [ ] `ExpenseOrderManager.delete_expense_order()` — L344
- [ ] `ExpenseOrderManager.add_item()` — L363
- [ ] `ExpenseOrderManager.update_item()` — L388
- [ ] `ExpenseOrderManager.remove_item()` — L416
- [ ] `ExpenseOrderManager.get_items()` — L438
- [ ] `ExpenseOrderManager._recalc_totals()` — L442 _(private)_
- [ ] `ExpenseOrderManager.list_approvers()` — L450
- [ ] `ExpenseOrderManager.approval_summary()` — L466
- [ ] `ExpenseOrderManager.approvals_met()` — L479
- [ ] `ExpenseOrderManager.add_approver()` — L482
- [ ] `ExpenseOrderManager.remove_approver()` — L521
- [ ] `ExpenseOrderManager.set_approval()` — L541
- [ ] `ExpenseOrderManager.log_event()` — L575
- [ ] `ExpenseOrderManager.list_events()` — L592
- [ ] `ExpenseOrderManager.create_expense_order_from_template()` — L605

### Services

#### `app/services/expense_order_service.py` (28)

#### class `ExpenseOrderService` (BaseService)

- [ ] `ExpenseOrderService.__init__()` — L33 _(dunder)_
- [ ] `ExpenseOrderService.create_expense_order()` — L38
- [ ] `ExpenseOrderService.update_expense_order()` — L51
- [ ] `ExpenseOrderService.get_expense_order()` — L78
- [ ] `ExpenseOrderService.list_expense_orders()` — L81
- [ ] `ExpenseOrderService._hub_filter_kwargs()` — L100 _(private)_
- [ ] `ExpenseOrderService.list_expense_orders_page()` — L127
- [ ] `ExpenseOrderService.get_expense_order_hub_stats()` — L171
- [ ] `ExpenseOrderService.delete_expense_order()` — L262
- [ ] `ExpenseOrderService.complete_expense_order()` — L270
- [ ] `ExpenseOrderService.void_expense_order()` — L316
- [ ] `ExpenseOrderService.add_item()` — L362
- [ ] `ExpenseOrderService.update_item()` — L380
- [ ] `ExpenseOrderService.remove_item()` — L398
- [ ] `ExpenseOrderService.get_items()` — L414
- [ ] `ExpenseOrderService._invoice_item_dicts()` — L417 _(private)_
- [ ] `ExpenseOrderService._create_draft_invoice()` — L433 _(private)_
- [ ] `ExpenseOrderService._resync_draft_invoice()` — L485 _(private)_
- [ ] `ExpenseOrderService._sync_or_create_invoice()` — L508 _(private)_
- [ ] `ExpenseOrderService.create_invoice_for_expense_order()` — L538
- [ ] `ExpenseOrderService.list_approvers()` — L574
- [ ] `ExpenseOrderService.approval_summary_for()` — L579
- [ ] `ExpenseOrderService.add_approver()` — L585
- [ ] `ExpenseOrderService.remove_approver()` — L610
- [ ] `ExpenseOrderService.approve_as_me()` — L622
- [ ] `ExpenseOrderService.unapprove_as_me()` — L637
- [ ] `ExpenseOrderService.list_events()` — L652
- [ ] `ExpenseOrderService.create_expense_order_from_template()` — L658

### DAOs

#### `app/dao/expense_order.py` (20)

#### class `ExpenseOrderDAO` (BaseDAO[ExpenseOrder, ExpenseOrderCreate, ExpenseOrderUpdate])

- [ ] `ExpenseOrderDAO.get_by_workspace()` — L185
- [ ] `ExpenseOrderDAO.list_for_hub()` — L205
- [ ] `ExpenseOrderDAO.count_for_hub()` — L226
- [ ] `ExpenseOrderDAO.list_recent_for_hub()` — L235
- [ ] `ExpenseOrderDAO.aggregate_hub_stats()` — L250
- [ ] `ExpenseOrderDAO._filtered_orders_query()` — L287 _(private)_
- [ ] `ExpenseOrderDAO.aggregate_financial_snapshot_filtered()` — L298
- [ ] `ExpenseOrderDAO.aggregate_financial_snapshot_actionable()` — L395
- [ ] `ExpenseOrderDAO.get_by_id_and_workspace()` — L490
- [ ] `ExpenseOrderDAO.get_next_number()` — L499

#### class `ExpenseOrderItemDAO` (BaseDAO[ExpenseOrderItem, ExpenseOrderItemCreate, ExpenseOrderItemUpdate])

- [ ] `ExpenseOrderItemDAO.get_by_order()` — L524
- [ ] `ExpenseOrderItemDAO.get_by_id_and_workspace()` — L537

#### module-level functions

- [ ] `_expense_order_is_complete_clause()` — L54 _(private)_
- [ ] `_expense_order_stage_key_expr()` — L58 _(private)_
- [ ] `_category_label()` — L67 _(private)_
- [ ] `_due_date_bucket()` — L71 _(private)_
- [ ] `_due_window_dates()` — L83 _(private)_
- [ ] `_apply_expense_order_stage_filter()` — L91 _(private)_
- [ ] `_apply_expense_order_hub_filters()` — L115 _(private)_
- [ ] `_hub_base_query()` — L179 _(private)_

#### `app/dao/expense_order_approver.py` (2)

#### class `ExpenseOrderApproverDAO` (BaseDAO[ExpenseOrderApprover, ExpenseOrderApproverCreate, ExpenseOrderApproverCreate])

- [ ] `ExpenseOrderApproverDAO.get_by_order()` — L10
- [ ] `ExpenseOrderApproverDAO.get_by_order_and_user()` — L23

#### `app/dao/expense_order_event.py` (1)

#### class `ExpenseOrderEventDAO` (BaseDAO[ExpenseOrderEvent, object, object])

- [ ] `ExpenseOrderEventDAO.get_by_order()` — L10

## Order Infrastructure & Workflow (84 callables)

### Managers

#### `app/managers/delivery_method_manager.py` (7)

#### class `DeliveryMethodManager` (BaseManager[DeliveryMethod])

- [ ] `DeliveryMethodManager.__init__()` — L23 _(dunder)_
- [ ] `DeliveryMethodManager.create_delivery_method()` — L27
- [ ] `DeliveryMethodManager.update_delivery_method()` — L55
- [ ] `DeliveryMethodManager.get_delivery_method()` — L99
- [ ] `DeliveryMethodManager.search_delivery_methods()` — L122
- [ ] `DeliveryMethodManager.delete_delivery_method()` — L148
- [ ] `DeliveryMethodManager._check_name_exists()` — L181 _(private)_

#### `app/managers/order_template_manager.py` (10)

#### class `OrderTemplateManager` (BaseManager[OrderTemplate])

- [ ] `OrderTemplateManager.__init__()` — L20 _(dunder)_
- [ ] `OrderTemplateManager.create_template()` — L25
- [ ] `OrderTemplateManager.update_template()` — L51
- [ ] `OrderTemplateManager.get_template()` — L64
- [ ] `OrderTemplateManager.list_templates()` — L70
- [ ] `OrderTemplateManager.delete_template()` — L82
- [ ] `OrderTemplateManager.add_item()` — L91
- [ ] `OrderTemplateManager.update_item()` — L114
- [ ] `OrderTemplateManager.remove_item()` — L131
- [ ] `OrderTemplateManager.get_items()` — L140

### Services

#### `app/services/approval_notification_service.py` (17)

#### module-level functions

- [ ] `format_order_ref()` — L30
- [ ] `_active_member_ids()` — L37 _(private)_
- [ ] `_notify_user()` — L44 _(private)_
- [ ] `_actor_name()` — L74 _(private)_
- [ ] `_approval_summary()` — L81 _(private)_
- [ ] `build_approval_preview()` — L107
- [ ] `_is_approval_ready()` — L116 _(private)_
- [ ] `_section_gap_preview()` — L136 _(private)_
- [ ] `_pending_approver_ids()` — L165 _(private)_
- [ ] `_has_approvers()` — L195 _(private)_
- [ ] `notify_approval_assigned()` — L200
- [ ] `notify_approval_pending_for_order()` — L233
- [ ] `notify_section_confirm_needed()` — L261
- [ ] `notify_invoice_action()` — L289
- [ ] `handle_add_approver()` — L360
- [ ] `handle_order_update_notifications()` — L403
- [ ] `detect_section_unconfirmed()` — L450

#### `app/services/delivery_method_service.py` (6)

#### class `DeliveryMethodService` (BaseService)

- [ ] `DeliveryMethodService.__init__()` — L21 _(dunder)_
- [ ] `DeliveryMethodService.create_delivery_method()` — L25
- [ ] `DeliveryMethodService.get_delivery_method()` — L54
- [ ] `DeliveryMethodService.get_delivery_methods()` — L67
- [ ] `DeliveryMethodService.update_delivery_method()` — L84
- [ ] `DeliveryMethodService.delete_delivery_method()` — L115

#### `app/services/order_hub_stats_helpers.py` (4)

#### module-level functions

- [ ] `purchase_order_to_recent_summary()` — L8
- [ ] `expense_order_to_recent_summary()` — L23
- [ ] `transfer_order_to_recent_summary()` — L40
- [ ] `pending_highlight_from_dict()` — L54

#### `app/services/order_template_service.py` (10)

#### class `OrderTemplateService` (BaseService)

- [ ] `OrderTemplateService.__init__()` — L18 _(dunder)_
- [ ] `OrderTemplateService.create_template()` — L22
- [ ] `OrderTemplateService.update_template()` — L35
- [ ] `OrderTemplateService.get_template()` — L48
- [ ] `OrderTemplateService.list_templates()` — L51
- [ ] `OrderTemplateService.delete_template()` — L63
- [ ] `OrderTemplateService.add_item()` — L72
- [ ] `OrderTemplateService.update_item()` — L85
- [ ] `OrderTemplateService.remove_item()` — L98
- [ ] `OrderTemplateService.get_items()` — L107

#### `app/services/order_workflow_service.py` (6)

#### class `OrderWorkflowService`

- [ ] `OrderWorkflowService.get_workflows()` — L10
- [ ] `OrderWorkflowService.get_by_id()` — L14
- [ ] `OrderWorkflowService.get_by_type()` — L18
- [ ] `OrderWorkflowService.create_workflow()` — L22
- [ ] `OrderWorkflowService.update_workflow()` — L35
- [ ] `OrderWorkflowService.delete_workflow()` — L49

#### `app/services/orders_overview_service.py` (9)

#### class `OrdersOverviewService`

- [ ] `OrdersOverviewService._po_report_date()` — L41 _(private)_
- [ ] `OrdersOverviewService._in_date_range()` — L44 _(private)_
- [ ] `OrdersOverviewService._filter_po_by_factory()` — L47 _(private)_
- [ ] `OrdersOverviewService._filter_transfer_by_factory()` — L77 _(private)_
- [ ] `OrdersOverviewService._factory_from_location()` — L121 _(private)_
- [ ] `OrdersOverviewService._accumulate_factory()` — L135 _(private)_
- [ ] `OrdersOverviewService._build_top_factories()` — L156 _(private)_
- [ ] `OrdersOverviewService.get_stats()` — L307

#### module-level functions

- [ ] `_dec()` — L34 _(private)_

#### `app/services/status_service.py` (5)

#### class `StatusService`

- [ ] `StatusService.get_statuses()` — L10
- [ ] `StatusService.get_by_id()` — L14
- [ ] `StatusService.create_status()` — L18
- [ ] `StatusService.update_status()` — L29
- [ ] `StatusService.delete_status()` — L43

### Utils

#### `app/utils/order_workflow_terminal.py` (2)

#### module-level functions

- [ ] `terminal_status_ids_by_workflow()` — L9
- [ ] `is_order_terminal()` — L38

### DAOs

#### `app/dao/delivery_method.py` (3)

#### class `DAODeliveryMethod` (BaseDAO[DeliveryMethod, DeliveryMethodCreate, DeliveryMethodUpdate])

- [x] `DAODeliveryMethod.get_active_delivery_methods()` — L25 ~~[DELETED DEAD CODE]~~
- [ ] `DAODeliveryMethod.soft_delete()` — L41
- [ ] `DAODeliveryMethod.restore()` — L52

#### `app/dao/order_template.py` (4)

#### class `OrderTemplateDAO` (BaseDAO[OrderTemplate, OrderTemplateCreate, OrderTemplateUpdate])

- [ ] `OrderTemplateDAO.get_by_workspace()` — L12
- [ ] `OrderTemplateDAO.get_by_id_and_workspace()` — L20

#### class `OrderTemplateItemDAO` (BaseDAO[OrderTemplateItem, OrderTemplateItemCreate, OrderTemplateItemUpdate])

- [ ] `OrderTemplateItemDAO.get_by_template()` — L25
- [ ] `OrderTemplateItemDAO.get_by_id_and_workspace()` — L28

#### `app/dao/order_workflow.py` (1)

#### class `DAOOrderWorkflow` (BaseDAO[OrderWorkflow, OrderWorkflowCreate, OrderWorkflowUpdate])

- [ ] `DAOOrderWorkflow.get_by_type()` — L17

#### `app/dao/status.py` (0)

#### class `DAOStatus` (BaseDAO[Status, StatusCreate, StatusUpdate])

_(no methods defined in class body)_


## Machines (83 callables)

### Managers

#### `app/managers/machine_activity_manager.py` (8)

#### class `MachineActivityManager`

- [ ] `MachineActivityManager.__init__()` — L34 _(dunder)_
- [ ] `MachineActivityManager.format_field_value()` — L39
- [ ] `MachineActivityManager.collect_field_changes()` — L50
- [ ] `MachineActivityManager.log_event()` — L74
- [ ] `MachineActivityManager.list_events()` — L96
- [ ] `MachineActivityManager.get_latest_status()` — L130
- [ ] `MachineActivityManager.get_latest_status_map()` — L143
- [ ] `MachineActivityManager.status_from_activity()` — L154

#### `app/managers/machine_item_manager.py` (8)

#### class `MachineItemManager`

- [ ] `MachineItemManager.__init__()` — L22 _(dunder)_
- [ ] `MachineItemManager._item_name()` — L28 _(private)_
- [ ] `MachineItemManager.get_machine_item()` — L34
- [ ] `MachineItemManager.list_machine_items()` — L45
- [ ] `MachineItemManager._write_ledger_entry()` — L60 _(private)_
- [ ] `MachineItemManager.create_machine_item()` — L126
- [ ] `MachineItemManager.update_machine_item()` — L189
- [ ] `MachineItemManager.delete_machine_item()` — L245

#### `app/managers/machine_maintenance_log_manager.py` (6)

#### class `MachineMaintenanceLogManager` (BaseManager[MachineMaintenanceLog])

- [ ] `MachineMaintenanceLogManager.__init__()` — L29 _(dunder)_
- [ ] `MachineMaintenanceLogManager.create_log()` — L34
- [ ] `MachineMaintenanceLogManager.update_log()` — L75
- [ ] `MachineMaintenanceLogManager.get_log()` — L117
- [ ] `MachineMaintenanceLogManager.list_logs()` — L131
- [ ] `MachineMaintenanceLogManager.delete_log()` — L160

#### `app/managers/machine_manager.py` (8)

#### class `MachineManager` (BaseManager[Machine])

- [ ] `MachineManager.__init__()` — L37 _(dunder)_
- [ ] `MachineManager.create_machine()` — L45
- [ ] `MachineManager.update_machine()` — L106
- [ ] `MachineManager.get_machine()` — L193
- [ ] `MachineManager.search_machines()` — L210
- [ ] `MachineManager.delete_machine()` — L336
- [ ] `MachineManager.create_machine_event()` — L371
- [ ] `MachineManager._check_name_exists_in_factory()` — L459 _(private)_

#### `app/managers/machine_section_assignment_manager.py` (4)

#### class `MachineSectionAssignmentManager`

- [ ] `MachineSectionAssignmentManager.__init__()` — L15 _(dunder)_
- [ ] `MachineSectionAssignmentManager.set_assignment()` — L19
- [x] `MachineSectionAssignmentManager.get_for_machine()` — L51 ~~[DELETED DEAD CODE]~~
- [ ] `MachineSectionAssignmentManager.clear_for_section()` — L56

### Services

#### `app/services/machine_item_service.py` (6)

#### class `MachineItemService` (BaseService)

- [ ] `MachineItemService.__init__()` — L14 _(dunder)_
- [ ] `MachineItemService.get_machine_item()` — L18
- [ ] `MachineItemService.get_machine_items()` — L26
- [ ] `MachineItemService.create_machine_item()` — L37
- [ ] `MachineItemService.update_machine_item()` — L56
- [ ] `MachineItemService.delete_machine_item()` — L77

#### `app/services/machine_maintenance_log_service.py` (6)

#### class `MachineMaintenanceLogService` (BaseService)

- [ ] `MachineMaintenanceLogService.__init__()` — L15 _(dunder)_
- [ ] `MachineMaintenanceLogService.create_log()` — L19
- [ ] `MachineMaintenanceLogService.update_log()` — L36
- [ ] `MachineMaintenanceLogService.get_log()` — L53
- [ ] `MachineMaintenanceLogService.list_logs()` — L59
- [ ] `MachineMaintenanceLogService.delete_log()` — L72

#### `app/services/machine_service.py` (11)

#### class `MachineService` (BaseService)

- [ ] `MachineService.__init__()` — L54 _(dunder)_
- [ ] `MachineService._to_machine_response()` — L64 _(private)_
- [ ] `MachineService._to_machine_responses()` — L101 _(private)_
- [ ] `MachineService.create_machine()` — L131
- [ ] `MachineService.get_machine()` — L165
- [ ] `MachineService.get_machines()` — L179
- [ ] `MachineService.get_upcoming_work()` — L239
- [ ] `MachineService.update_machine()` — L281
- [ ] `MachineService.delete_machine()` — L317
- [ ] `MachineService.create_machine_event()` — L355
- [ ] `MachineService.get_machine_activity()` — L387

### DAOs

#### `app/dao/machine.py` (7)

#### class `DAOMachine` (BaseDAO[Machine, MachineCreate, MachineUpdate])

- [ ] `DAOMachine.get_by_factory()` — L26
- [ ] `DAOMachine.get_by_section()` — L39
- [x] `DAOMachine.get_running_machines()` — L54 ~~[DELETED DEAD CODE]~~
- [ ] `DAOMachine.get_active_by_workspace()` — L69
- [ ] `DAOMachine.soft_delete()` — L83
- [ ] `DAOMachine.restore()` — L95
- [ ] `DAOMachine.search_advanced()` — L107

#### `app/dao/machine_activity_event.py` (3)

#### class `MachineActivityEventDAO` (BaseDAO[MachineActivityEvent, MachineActivityEventResponse, MachineActivityEventResponse])

- [ ] `MachineActivityEventDAO.get_by_machine()` — L16
- [ ] `MachineActivityEventDAO.get_latest_status_by_machine()` — L45
- [ ] `MachineActivityEventDAO.get_latest_status_map()` — L63

#### `app/dao/machine_item.py` (5)

#### class `DAOMachineItem` (BaseDAO[MachineItem, MachineItemCreate, MachineItemUpdate])

- [ ] `DAOMachineItem.get_by_workspace()` — L12
- [ ] `DAOMachineItem.get_by_id_and_workspace()` — L22
- [ ] `DAOMachineItem.get_by_machine()` — L35
- [ ] `DAOMachineItem.get_by_machine_and_item()` — L48
- [ ] `DAOMachineItem.get_by_item()` — L62

#### `app/dao/machine_maintenance_log.py` (7)

#### class `MachineMaintenanceLogDAO` (BaseDAO[MachineMaintenanceLog, MachineMaintenanceLogCreate, MachineMaintenanceLogUpdate])

- [ ] `MachineMaintenanceLogDAO.get_by_workspace()` — L18
- [ ] `MachineMaintenanceLogDAO.get_by_id_and_workspace()` — L27
- [ ] `MachineMaintenanceLogDAO.get_by_machine()` — L36
- [ ] `MachineMaintenanceLogDAO.get_by_type()` — L46
- [ ] `MachineMaintenanceLogDAO.get_by_machine_and_type()` — L56
- [ ] `MachineMaintenanceLogDAO.soft_delete()` — L68
- [ ] `MachineMaintenanceLogDAO.restore()` — L79

#### `app/dao/machine_section_assignment.py` (4)

#### class `DAOMachineSectionAssignment` (BaseDAO[MachineSectionAssignment, MachineSectionAssignmentCreate, MachineSectionAssignmentCreate])

- [ ] `DAOMachineSectionAssignment.get_by_machine()` — L15
- [ ] `DAOMachineSectionAssignment.get_by_section()` — L23
- [ ] `DAOMachineSectionAssignment.upsert_for_machine()` — L36
- [ ] `DAOMachineSectionAssignment.clear_for_section()` — L56

## Projects (82 callables)

### Managers

#### `app/managers/project_component_activity_manager.py` (3)

#### class `ProjectComponentActivityManager`

- [ ] `ProjectComponentActivityManager.__init__()` — L18 _(dunder)_
- [ ] `ProjectComponentActivityManager.log_event()` — L22
- [ ] `ProjectComponentActivityManager.list_events()` — L44

#### `app/managers/project_manager.py` (22)

#### class `ProjectManager` (BaseManager[Project])

- [ ] `ProjectManager.__init__()` — L46 _(dunder)_
- [ ] `ProjectManager._visibility_value()` — L53 _(private)_
- [ ] `ProjectManager._is_workspace_owner()` — L61 _(private)_
- [ ] `ProjectManager._is_privileged()` — L65 _(private)_
- [ ] `ProjectManager.can_access_project()` — L73
- [ ] `ProjectManager._get_project_or_404()` — L95 _(private)_
- [ ] `ProjectManager.require_project_access()` — L111
- [ ] `ProjectManager.require_component_access()` — L126
- [ ] `ProjectManager._format_field_value()` — L148 _(private)_
- [ ] `ProjectManager._collect_field_changes()` — L157 _(private)_
- [ ] `ProjectManager.log_for_component()` — L179
- [ ] `ProjectManager.log_event()` — L209
- [ ] `ProjectManager.list_events()` — L231
- [ ] `ProjectManager.list_members()` — L247
- [ ] `ProjectManager.add_member()` — L259
- [ ] `ProjectManager.remove_member()` — L308
- [ ] `ProjectManager.set_visibility()` — L348
- [ ] `ProjectManager.create_project()` — L388
- [ ] `ProjectManager.get_project()` — L436
- [ ] `ProjectManager.list_projects()` — L445
- [ ] `ProjectManager.update_project()` — L485
- [ ] `ProjectManager.delete_project()` — L536

### Services

#### `app/services/miscellaneous_project_cost_service.py` (7)

#### class `MiscellaneousProjectCostService`

- [ ] `MiscellaneousProjectCostService._log_cost_activity()` — L15 _(private)_
- [ ] `MiscellaneousProjectCostService._filter_accessible_costs()` — L48 _(private)_
- [ ] `MiscellaneousProjectCostService.get_costs()` — L68
- [ ] `MiscellaneousProjectCostService.get_by_id()` — L106
- [ ] `MiscellaneousProjectCostService.create_cost()` — L124
- [ ] `MiscellaneousProjectCostService.update_cost()` — L158
- [ ] `MiscellaneousProjectCostService.delete_cost()` — L186

#### `app/services/project_component_item_service.py` (7)

#### class `ProjectComponentItemService`

- [ ] `ProjectComponentItemService._guard_component()` — L12 _(private)_
- [ ] `ProjectComponentItemService._filter_accessible_items()` — L15 _(private)_
- [ ] `ProjectComponentItemService.get_items()` — L32
- [ ] `ProjectComponentItemService.get_by_id()` — L56
- [ ] `ProjectComponentItemService.create_component_item()` — L65
- [ ] `ProjectComponentItemService.update_component_item()` — L95
- [ ] `ProjectComponentItemService.delete_component_item()` — L124

#### `app/services/project_component_note_service.py` (7)

#### class `ProjectComponentNoteService`

- [ ] `ProjectComponentNoteService._guard_component()` — L12 _(private)_
- [ ] `ProjectComponentNoteService._filter_accessible_notes()` — L15 _(private)_
- [ ] `ProjectComponentNoteService.get_notes()` — L32
- [ ] `ProjectComponentNoteService.get_by_id_and_workspace()` — L66
- [ ] `ProjectComponentNoteService.create_note()` — L77
- [ ] `ProjectComponentNoteService.update_note()` — L108
- [ ] `ProjectComponentNoteService.delete_note()` — L137

#### `app/services/project_component_service.py` (5)

#### class `ProjectComponentService`

- [ ] `ProjectComponentService.get_components()` — L11
- [ ] `ProjectComponentService.get_by_id()` — L46
- [ ] `ProjectComponentService.create_component()` — L54
- [ ] `ProjectComponentService.update_component()` — L84
- [ ] `ProjectComponentService.delete_component()` — L119

#### `app/services/project_component_task_service.py` (7)

#### class `ProjectComponentTaskService`

- [ ] `ProjectComponentTaskService._guard_component()` — L12 _(private)_
- [ ] `ProjectComponentTaskService._filter_accessible_tasks()` — L15 _(private)_
- [ ] `ProjectComponentTaskService.get_tasks()` — L32
- [ ] `ProjectComponentTaskService.get_by_id()` — L68
- [ ] `ProjectComponentTaskService.create_task()` — L77
- [ ] `ProjectComponentTaskService.update_task()` — L108
- [ ] `ProjectComponentTaskService.delete_task()` — L150

#### `app/services/project_service.py` (11)

#### class `ProjectService` (BaseService)

- [ ] `ProjectService.__init__()` — L22 _(dunder)_
- [ ] `ProjectService.create_project()` — L26
- [ ] `ProjectService.get_project()` — L47
- [ ] `ProjectService.list_projects()` — L61
- [ ] `ProjectService.update_project()` — L81
- [ ] `ProjectService.delete_project()` — L104
- [ ] `ProjectService.list_events()` — L125
- [ ] `ProjectService.list_members()` — L139
- [ ] `ProjectService.add_member()` — L153
- [ ] `ProjectService.remove_member()` — L176
- [ ] `ProjectService.set_visibility()` — L197

### DAOs

#### `app/dao/miscellaneous_project_cost.py` (2)

#### class `DAOMiscellaneousProjectCost` (BaseDAO[MiscellaneousProjectCost, MiscellaneousProjectCostCreate, MiscellaneousProjectCostUpdate])

- [ ] `DAOMiscellaneousProjectCost.get_by_project()` — L17
- [ ] `DAOMiscellaneousProjectCost.get_by_component()` — L44

#### `app/dao/project.py` (2)

#### class `DAOProject` (BaseDAO[Project, ProjectCreate, ProjectUpdate])

- [ ] `DAOProject.get_by_factory()` — L17
- [ ] `DAOProject.get_by_status()` — L44

#### `app/dao/project_component.py` (1)

#### class `DAOProjectComponent` (BaseDAO[ProjectComponent, ProjectComponentCreate, ProjectComponentUpdate])

- [ ] `DAOProjectComponent.get_by_project()` — L12

#### `app/dao/project_component_activity_event.py` (1)

#### class `ProjectComponentActivityEventDAO` (BaseDAO[ProjectComponentActivityEvent, object, object])

- [ ] `ProjectComponentActivityEventDAO.get_by_component()` — L12

#### `app/dao/project_component_item.py` (1)

#### class `DAOProjectComponentItem` (BaseDAO[ProjectComponentItem, ProjectComponentItemCreate, ProjectComponentItemUpdate])

- [ ] `DAOProjectComponentItem.get_by_component()` — L12

#### `app/dao/project_component_task.py` (2)

#### class `DAOProjectComponentTask` (BaseDAO[ProjectComponentTask, ProjectComponentTaskCreate, ProjectComponentTaskUpdate])

- [ ] `DAOProjectComponentTask.get_by_component()` — L17
- [ ] `DAOProjectComponentTask.get_incomplete_tasks()` — L40

#### `app/dao/project_event.py` (1)

#### class `ProjectEventDAO` (BaseDAO[ProjectEvent, ProjectEventResponse, ProjectEventResponse])

- [ ] `ProjectEventDAO.get_by_project()` — L11

#### `app/dao/project_member.py` (3)

#### class `ProjectMemberDAO` (BaseDAO[ProjectMember, ProjectMemberCreate, ProjectMemberCreate])

- [ ] `ProjectMemberDAO.get_by_project()` — L10
- [ ] `ProjectMemberDAO.get_by_project_and_user()` — L23
- [x] `ProjectMemberDAO.get_project_ids_for_user()` — L36 ~~[DELETED DEAD CODE]~~

## Production (125 callables)

### Managers

#### `app/managers/production_batch_manager.py` (21)

#### class `ProductionBatchManager` (BaseManager[ProductionBatch])

- [ ] `ProductionBatchManager.__init__()` — L47 _(dunder)_
- [ ] `ProductionBatchManager.create_batch()` — L58
- [ ] `ProductionBatchManager.update_batch()` — L116
- [ ] `ProductionBatchManager.get_batch()` — L154
- [ ] `ProductionBatchManager.get_batches()` — L165
- [ ] `ProductionBatchManager.get_batch_stats()` — L196
- [ ] `ProductionBatchManager.delete_batch()` — L210
- [ ] `ProductionBatchManager.start_batch()` — L239
- [ ] `ProductionBatchManager.complete_batch()` — L366
- [ ] `ProductionBatchManager.cancel_batch()` — L499
- [ ] `ProductionBatchManager.add_batch_item()` — L531
- [ ] `ProductionBatchManager.update_batch_item()` — L570
- [ ] `ProductionBatchManager.remove_batch_item()` — L600
- [ ] `ProductionBatchManager.get_batch_items()` — L621
- [ ] `ProductionBatchManager._calculate_batch_item_variances()` — L650 _(private)_
- [ ] `ProductionBatchManager.post_outputs_to_finished_goods()` — L669
- [ ] `ProductionBatchManager._seed_stage_logs_from_formula()` — L757 _(private)_
- [ ] `ProductionBatchManager.get_batch_stage_logs()` — L780
- [ ] `ProductionBatchManager.add_batch_stage_log()` — L792
- [ ] `ProductionBatchManager.update_batch_stage_log()` — L822
- [ ] `ProductionBatchManager._validate_stage_log_completion()` — L857 _(private)_

#### `app/managers/production_formula_manager.py` (17)

#### class `ProductionFormulaManager` (BaseManager[ProductionFormula])

- [ ] `ProductionFormulaManager.__init__()` — L31 _(dunder)_
- [ ] `ProductionFormulaManager.create_formula()` — L39
- [ ] `ProductionFormulaManager.update_formula()` — L74
- [ ] `ProductionFormulaManager.get_formula()` — L104
- [ ] `ProductionFormulaManager.get_formulas()` — L115
- [ ] `ProductionFormulaManager.delete_formula()` — L133
- [ ] `ProductionFormulaManager.add_formula_item()` — L157
- [ ] `ProductionFormulaManager.update_formula_item()` — L198
- [ ] `ProductionFormulaManager.remove_formula_item()` — L222
- [ ] `ProductionFormulaManager.get_formula_items()` — L237
- [x] `ProductionFormulaManager.get_formula_base_output()` — L265 ~~[DELETED DEAD CODE]~~
- [ ] `ProductionFormulaManager._validate_stage_refs()` — L295 _(private)_
- [ ] `ProductionFormulaManager.get_formula_stages()` — L326
- [ ] `ProductionFormulaManager.add_formula_stage()` — L338
- [ ] `ProductionFormulaManager.update_formula_stage()` — L368
- [ ] `ProductionFormulaManager.remove_formula_stage()` — L404
- [ ] `ProductionFormulaManager._clear_other_defaults()` — L416 _(private)_

#### `app/managers/production_line_manager.py` (6)

#### class `ProductionLineManager` (BaseManager[ProductionLine])

- [ ] `ProductionLineManager.__init__()` — L23 _(dunder)_
- [ ] `ProductionLineManager.create_production_line()` — L27
- [ ] `ProductionLineManager.update_production_line()` — L82
- [ ] `ProductionLineManager.get_production_line()` — L140
- [ ] `ProductionLineManager.get_production_lines()` — L164
- [ ] `ProductionLineManager.delete_production_line()` — L200

### Services

#### `app/services/production_batch_service.py` (18)

#### class `ProductionBatchService` (BaseService)

- [ ] `ProductionBatchService.__init__()` — L22 _(dunder)_
- [ ] `ProductionBatchService.create_batch()` — L28
- [ ] `ProductionBatchService.get_batch()` — L53
- [ ] `ProductionBatchService.get_batches()` — L65
- [ ] `ProductionBatchService.get_batch_stats()` — L86
- [ ] `ProductionBatchService.update_batch()` — L96
- [ ] `ProductionBatchService.delete_batch()` — L126
- [ ] `ProductionBatchService.start_batch()` — L152
- [ ] `ProductionBatchService.complete_batch()` — L186
- [ ] `ProductionBatchService.post_outputs_to_finished_goods()` — L226
- [ ] `ProductionBatchService.cancel_batch()` — L261
- [ ] `ProductionBatchService.add_batch_item()` — L293
- [ ] `ProductionBatchService.update_batch_item()` — L319
- [ ] `ProductionBatchService.remove_batch_item()` — L347
- [ ] `ProductionBatchService.get_batch_items()` — L371
- [ ] `ProductionBatchService.get_batch_stage_logs()` — L394
- [ ] `ProductionBatchService.add_batch_stage_log()` — L402
- [ ] `ProductionBatchService.update_batch_stage_log()` — L424

#### `app/services/production_formula_service.py` (14)

#### class `ProductionFormulaService` (BaseService)

- [ ] `ProductionFormulaService.__init__()` — L21 _(dunder)_
- [ ] `ProductionFormulaService.create_formula()` — L27
- [ ] `ProductionFormulaService.get_formula()` — L52
- [ ] `ProductionFormulaService.get_formulas()` — L64
- [ ] `ProductionFormulaService.update_formula()` — L81
- [ ] `ProductionFormulaService.delete_formula()` — L111
- [ ] `ProductionFormulaService.add_formula_item()` — L136
- [ ] `ProductionFormulaService.update_formula_item()` — L162
- [ ] `ProductionFormulaService.remove_formula_item()` — L190
- [ ] `ProductionFormulaService.get_formula_items()` — L211
- [ ] `ProductionFormulaService.get_formula_stages()` — L234
- [ ] `ProductionFormulaService.add_formula_stage()` — L242
- [ ] `ProductionFormulaService.update_formula_stage()` — L260
- [ ] `ProductionFormulaService.remove_formula_stage()` — L282

#### `app/services/production_line_service.py` (6)

#### class `ProductionLineService` (BaseService)

- [ ] `ProductionLineService.__init__()` — L20 _(dunder)_
- [ ] `ProductionLineService.create_production_line()` — L24
- [ ] `ProductionLineService.get_production_line()` — L66
- [ ] `ProductionLineService.get_production_lines()` — L93
- [ ] `ProductionLineService.update_production_line()` — L125
- [ ] `ProductionLineService.delete_production_line()` — L174

### DAOs

#### `app/dao/production_batch.py` (11)

#### class `ProductionBatchDAO` (BaseDAO[ProductionBatch, ProductionBatchCreate, ProductionBatchUpdate])

- [ ] `ProductionBatchDAO.get_by_workspace()` — L18
- [x] `ProductionBatchDAO.get_by_batch_number()` — L42 ~~[DELETED DEAD CODE]~~
- [ ] `ProductionBatchDAO.get_by_production_line()` — L65
- [ ] `ProductionBatchDAO.get_by_formula()` — L94
- [ ] `ProductionBatchDAO.get_by_status()` — L123
- [ ] `ProductionBatchDAO.count_by_status()` — L152
- [ ] `ProductionBatchDAO.get_by_date_range()` — L170
- [x] `ProductionBatchDAO.get_in_progress_batches()` — L201 ~~[DELETED DEAD CODE]~~
- [x] `ProductionBatchDAO.get_completed_batches()` — L224 ~~[DELETED DEAD CODE]~~
- [ ] `ProductionBatchDAO.get_by_id_and_workspace()` — L251
- [ ] `ProductionBatchDAO.generate_batch_number()` — L274

#### `app/dao/production_batch_item.py` (8)

#### class `ProductionBatchItemDAO` (BaseDAO[ProductionBatchItem, ProductionBatchItemCreate, ProductionBatchItemUpdate])

- [ ] `ProductionBatchItemDAO.get_by_batch()` — L15
- [ ] `ProductionBatchItemDAO.get_by_batch_and_role()` — L38
- [x] `ProductionBatchItemDAO.get_inputs_for_batch()` — L63 ~~[DELETED DEAD CODE]~~
- [x] `ProductionBatchItemDAO.get_outputs_for_batch()` — L81 ~~[DELETED DEAD CODE]~~
- [x] `ProductionBatchItemDAO.get_waste_for_batch()` — L99 ~~[DELETED DEAD CODE]~~
- [x] `ProductionBatchItemDAO.get_byproducts_for_batch()` — L117 ~~[DELETED DEAD CODE]~~
- [ ] `ProductionBatchItemDAO.get_by_item()` — L135
- [ ] `ProductionBatchItemDAO.get_by_id_and_workspace()` — L163

#### `app/dao/production_batch_stage_log.py` (2)

#### class `ProductionBatchStageLogDAO` (BaseDAO[ProductionBatchStageLog, ProductionBatchStageLogCreate, ProductionBatchStageLogUpdate])

- [ ] `ProductionBatchStageLogDAO.get_by_batch()` — L15
- [ ] `ProductionBatchStageLogDAO.get_by_id_and_workspace()` — L28

#### `app/dao/production_formula.py` (6)

#### class `ProductionFormulaDAO` (BaseDAO[ProductionFormula, ProductionFormulaCreate, ProductionFormulaUpdate])

- [ ] `ProductionFormulaDAO.get_by_workspace()` — L15
- [ ] `ProductionFormulaDAO.get_by_formula_code()` — L38
- [ ] `ProductionFormulaDAO.get_active_by_workspace()` — L61
- [ ] `ProductionFormulaDAO.get_default_formulas()` — L87
- [ ] `ProductionFormulaDAO.get_by_id_and_workspace()` — L110
- [x] `ProductionFormulaDAO.get_formula_versions()` — L133 ~~[DELETED DEAD CODE]~~

#### `app/dao/production_formula_item.py` (7)

#### class `ProductionFormulaItemDAO` (BaseDAO[ProductionFormulaItem, ProductionFormulaItemCreate, ProductionFormulaItemUpdate])

- [ ] `ProductionFormulaItemDAO.get_by_formula()` — L15
- [ ] `ProductionFormulaItemDAO.get_by_formula_and_role()` — L38
- [x] `ProductionFormulaItemDAO.get_inputs_for_formula()` — L63 ~~[DELETED DEAD CODE]~~
- [x] `ProductionFormulaItemDAO.get_outputs_for_formula()` — L81 ~~[DELETED DEAD CODE]~~
- [x] `ProductionFormulaItemDAO.get_waste_for_formula()` — L99 ~~[DELETED DEAD CODE]~~
- [x] `ProductionFormulaItemDAO.get_byproducts_for_formula()` — L117 ~~[DELETED DEAD CODE]~~
- [ ] `ProductionFormulaItemDAO.get_by_id_and_workspace()` — L135

#### `app/dao/production_formula_stage.py` (3)

#### class `ProductionFormulaStageDAO` (BaseDAO[ProductionFormulaStage, ProductionFormulaStageCreate, ProductionFormulaStageUpdate])

- [ ] `ProductionFormulaStageDAO.get_by_formula()` — L12
- [ ] `ProductionFormulaStageDAO.get_by_id_and_workspace()` — L25
- [x] `ProductionFormulaStageDAO.get_max_stage_order()` — L34 ~~[DELETED DEAD CODE]~~

#### `app/dao/production_line.py` (6)

#### class `ProductionLineDAO` (BaseDAO[ProductionLine, ProductionLineCreate, ProductionLineUpdate])

- [ ] `ProductionLineDAO.get_by_workspace()` — L15
- [ ] `ProductionLineDAO.get_by_factory()` — L38
- [ ] `ProductionLineDAO.get_by_machine()` — L65
- [ ] `ProductionLineDAO.get_active_by_workspace()` — L88
- [x] `ProductionLineDAO.get_standalone_lines()` — L114 ~~[DELETED DEAD CODE]~~
- [ ] `ProductionLineDAO.get_by_id_and_workspace()` — L136

## Invoicing & Accounts Receivable (85 callables)

### Managers

#### `app/managers/account_invoice_manager.py` (22)

#### class `AccountInvoiceManager` (BaseManager[AccountInvoice])

- [ ] `AccountInvoiceManager.__init__()` — L28 _(dunder)_
- [ ] `AccountInvoiceManager._get_or_404()` — L37 _(private)_
- [ ] `AccountInvoiceManager._log_event()` — L48 _(private)_
- [ ] `AccountInvoiceManager._recalculate_payment_status()` — L67 _(private)_
- [ ] `AccountInvoiceManager._recalculate_invoice_amount()` — L75 _(private)_
- [ ] `AccountInvoiceManager.create_invoice()` — L86
- [ ] `AccountInvoiceManager.get_invoice()` — L127
- [ ] `AccountInvoiceManager.list_invoices()` — L130
- [ ] `AccountInvoiceManager.list_open_invoices_page()` — L168
- [ ] `AccountInvoiceManager.list_invoices_page()` — L188
- [ ] `AccountInvoiceManager.get_invoices_hub_summary()` — L231
- [ ] `AccountInvoiceManager.list_accounts_hub_page()` — L244
- [ ] `AccountInvoiceManager.summarize_invoices()` — L263
- [ ] `AccountInvoiceManager.update_invoice()` — L297
- [ ] `AccountInvoiceManager.delete_invoice()` — L382
- [ ] `AccountInvoiceManager.confirm_invoice()` — L405
- [ ] `AccountInvoiceManager.revert_to_draft()` — L436
- [ ] `AccountInvoiceManager.void_invoice()` — L472
- [ ] `AccountInvoiceManager.set_receiving_started()` — L522
- [ ] `AccountInvoiceManager.sync_items_from_list()` — L549
- [ ] `AccountInvoiceManager.get_events()` — L605
- [ ] `AccountInvoiceManager.get_items()` — L609

#### `app/managers/invoice_payment_manager.py` (8)

#### class `InvoicePaymentManager` (BaseManager[InvoicePayment])

- [ ] `InvoicePaymentManager.__init__()` — L30 _(dunder)_
- [ ] `InvoicePaymentManager.create_payment()` — L35
- [ ] `InvoicePaymentManager.update_payment()` — L158
- [ ] `InvoicePaymentManager.get_payment()` — L205
- [ ] `InvoicePaymentManager.list_payments_by_invoice()` — L237
- [ ] `InvoicePaymentManager.delete_payment()` — L272
- [ ] `InvoicePaymentManager.void_payment()` — L368
- [ ] `InvoicePaymentManager._sync_linked_order()` — L455 _(private)_

### Services

#### `app/services/account_invoice_service.py` (17)

#### class `AccountInvoiceService` (BaseService)

- [ ] `AccountInvoiceService.__init__()` — L26 _(dunder)_
- [ ] `AccountInvoiceService.create_invoice()` — L30
- [ ] `AccountInvoiceService.get_invoice()` — L71
- [ ] `AccountInvoiceService.list_invoices()` — L93
- [ ] `AccountInvoiceService.list_open_invoices_page()` — L132
- [ ] `AccountInvoiceService.list_account_invoices_page()` — L151
- [ ] `AccountInvoiceService.get_invoices_hub_summary()` — L184
- [ ] `AccountInvoiceService.list_accounts_hub_page()` — L189
- [ ] `AccountInvoiceService.summarize_invoices()` — L207
- [ ] `AccountInvoiceService.update_invoice()` — L242
- [ ] `AccountInvoiceService.delete_invoice()` — L286
- [ ] `AccountInvoiceService.get_events()` — L333
- [ ] `AccountInvoiceService.get_items()` — L338
- [ ] `AccountInvoiceService.revert_to_draft()` — L343
- [ ] `AccountInvoiceService.resync_items()` — L355
- [ ] `AccountInvoiceService.confirm_invoice()` — L423
- [ ] `AccountInvoiceService.void_invoice()` — L494

#### `app/services/invoice_payment_service.py` (9)

#### class `InvoicePaymentService` (BaseService)

- [ ] `InvoicePaymentService.__init__()` — L37 _(dunder)_
- [ ] `InvoicePaymentService._payment_response()` — L41 _(private)_
- [ ] `InvoicePaymentService.create_payment()` — L55
- [ ] `InvoicePaymentService.get_payment()` — L76
- [ ] `InvoicePaymentService.list_payments_by_invoice()` — L93
- [ ] `InvoicePaymentService.update_payment()` — L110
- [ ] `InvoicePaymentService.delete_payment()` — L131
- [ ] `InvoicePaymentService.void_payment()` — L160

#### module-level functions

- [ ] `to_payment_response()` — L19

### DAOs

#### `app/dao/account_invoice.py` (18)

#### class `AccountInvoiceDAO` (BaseDAO[AccountInvoice, AccountInvoiceCreate, AccountInvoiceUpdate])

- [ ] `AccountInvoiceDAO._escape_ilike()` — L23 _(private)_
- [ ] `AccountInvoiceDAO._invoice_number_search_ilike_term()` — L30 _(private)_
- [ ] `AccountInvoiceDAO._outstanding_amount_expr()` — L37 _(private)_
- [ ] `AccountInvoiceDAO._order_number_search_conditions()` — L41 _(private)_
- [ ] `AccountInvoiceDAO._build_filtered_query()` — L75 _(private)_
- [ ] `AccountInvoiceDAO.list_invoices()` — L152
- [ ] `AccountInvoiceDAO.list_invoices_page()` — L197
- [ ] `AccountInvoiceDAO._open_balance_subquery()` — L219 _(private)_
- [ ] `AccountInvoiceDAO.list_accounts_hub_page()` — L243
- [ ] `AccountInvoiceDAO._reshape_accounts_hub_row()` — L291 _(private)_
- [ ] `AccountInvoiceDAO.summarize_open_hub_type()` — L307
- [ ] `AccountInvoiceDAO.count_accounts_with_any_open_balance()` — L332
- [ ] `AccountInvoiceDAO.list_invoices_page_filtered()` — L348
- [ ] `AccountInvoiceDAO.summarize_invoices()` — L413
- [ ] `AccountInvoiceDAO.get_by_order()` — L467
- [ ] `AccountInvoiceDAO.update_paid_amount()` — L480
- [x] `AccountInvoiceDAO.get_overdue_invoices()` — L496 ~~[DELETED DEAD CODE]~~
- [x] `AccountInvoiceDAO.get_invoices_with_payments_enabled()` — L522 ~~[DELETED DEAD CODE]~~

#### `app/dao/invoice_event.py` (2)

#### class `InvoiceEventDAO` (BaseDAO[InvoiceEvent, dict, dict])

- [ ] `InvoiceEventDAO.create_event()` — L12
- [ ] `InvoiceEventDAO.get_by_invoice()` — L35

#### `app/dao/invoice_item.py` (3)

#### class `InvoiceItemDAO` (BaseDAO[InvoiceItem, InvoiceItemCreate, InvoiceItemUpdate])

- [ ] `InvoiceItemDAO.get_by_invoice()` — L12
- [ ] `InvoiceItemDAO.get_by_id_and_workspace()` — L20
- [ ] `InvoiceItemDAO.delete_all_for_invoice()` — L27

#### `app/dao/invoice_payment.py` (6)

#### class `InvoicePaymentDAO` (BaseDAO[InvoicePayment, InvoicePaymentCreate, InvoicePaymentUpdate])

- [ ] `InvoicePaymentDAO.get_by_invoice()` — L16
- [ ] `InvoicePaymentDAO.get_by_id_and_workspace_with_creator()` — L39
- [ ] `InvoicePaymentDAO.get_by_date_range()` — L57
- [x] `InvoicePaymentDAO.get_by_payment_method()` — L88 ~~[DELETED DEAD CODE]~~
- [ ] `InvoicePaymentDAO.get_total_paid_for_invoice()` — L117
- [x] `InvoicePaymentDAO.get_recent_payments()` — L142 ~~[DELETED DEAD CODE]~~

## Subscription Billing & Payment Gateway (39 callables)

### Managers

#### `app/managers/payment_transaction_manager.py` (9)

#### class `PaymentTransactionManager` (BaseManager[PaymentTransaction])

- [ ] `PaymentTransactionManager.__init__()` — L33 _(dunder)_
- [ ] `PaymentTransactionManager._log_event()` — L38 _(private)_
- [ ] `PaymentTransactionManager._generate_tran_id()` — L56 _(private)_
- [ ] `PaymentTransactionManager.initiate_payment()` — L63
- [ ] `PaymentTransactionManager._apply_validation_result()` — L120 _(private)_
- [ ] `PaymentTransactionManager.finalize_from_gateway()` — L187
- [ ] `PaymentTransactionManager.mark_terminal_without_validation()` — L210
- [ ] `PaymentTransactionManager.resolve_risk()` — L233
- [ ] `PaymentTransactionManager.reconcile_stuck_transactions()` — L259

### Services

#### `app/services/payment_transaction_service.py` (8)

#### class `PaymentTransactionService` (BaseService)

- [ ] `PaymentTransactionService.__init__()` — L27 _(dunder)_
- [ ] `PaymentTransactionService.initiate_payment()` — L31
- [ ] `PaymentTransactionService.handle_gateway_callback()` — L45
- [ ] `PaymentTransactionService.handle_terminal_without_validation()` — L55
- [ ] `PaymentTransactionService.resolve_risk()` — L69
- [ ] `PaymentTransactionService.get_transaction_by_tran_id()` — L84
- [ ] `PaymentTransactionService.list_transactions()` — L100

#### module-level functions

- [ ] `_to_response()` — L22 _(private)_

### Integrations

#### `app/integrations/sslcommerz/__init__.py` (1)

#### module-level functions

- [ ] `get_sslcommerz_client()` — L14

#### `app/integrations/sslcommerz/client.py` (4)

#### class `InitSessionRequest`

_(no methods defined in class body)_


#### class `InitSessionResult`

_(no methods defined in class body)_


#### class `ValidationResult`

_(no methods defined in class body)_


#### class `SSLCommerzClient` (ABC)

- [ ] `SSLCommerzClient.init_session()` — L61
- [ ] `SSLCommerzClient.validate()` — L67
- [ ] `SSLCommerzClient.query_by_tran_id()` — L74
- [ ] `SSLCommerzClient.verify_signature()` — L81

#### `app/integrations/sslcommerz/mock_client.py` (7)

#### class `MockSSLCommerzClient` (SSLCommerzClient)

- [ ] `MockSSLCommerzClient.init_session()` — L35
- [ ] `MockSSLCommerzClient.build_val_id()` — L42
- [ ] `MockSSLCommerzClient._decode_val_id()` — L65 _(private)_
- [ ] `MockSSLCommerzClient.validate()` — L75
- [ ] `MockSSLCommerzClient.query_by_tran_id()` — L95
- [ ] `MockSSLCommerzClient.verify_signature()` — L102

#### module-level functions

- [ ] `_sign()` — L29 _(private)_

### DAOs

#### `app/dao/payment_transaction.py` (6)

#### class `PaymentTransactionDAO` (BaseDAO[PaymentTransaction, InitiatePaymentRequest, dict])

- [ ] `PaymentTransactionDAO.get_by_tran_id()` — L20
- [ ] `PaymentTransactionDAO.get_by_tran_id_for_update()` — L23
- [ ] `PaymentTransactionDAO.get_by_id_and_workspace_with_initiator()` — L33
- [ ] `PaymentTransactionDAO.get_by_tran_id_and_workspace_with_initiator()` — L46
- [ ] `PaymentTransactionDAO.list_by_workspace_with_initiator()` — L59
- [ ] `PaymentTransactionDAO.get_stuck_initiated()` — L73

#### `app/dao/payment_transaction_event.py` (1)

#### class `PaymentTransactionEventDAO` (BaseDAO[PaymentTransactionEvent, dict, dict])

- [ ] `PaymentTransactionEventDAO.get_by_payment_transaction()` — L9

#### `app/dao/subscription_plan.py` (3)

#### class `SubscriptionPlanDAO` (BaseDAO[SubscriptionPlan, SubscriptionPlanCreate, SubscriptionPlanUpdate])

- [ ] `SubscriptionPlanDAO.get_by_name()` — L12
- [ ] `SubscriptionPlanDAO.get_default_plan()` — L16
- [x] `SubscriptionPlanDAO.get_active_plans()` — L24 ~~[DELETED DEAD CODE]~~

## Notifications & Discussions (16 callables)

### Services

#### `app/services/discussion_service.py` (3)

#### class `DiscussionService`

- [ ] `DiscussionService.list()` — L25
- [ ] `DiscussionService.create()` — L38

#### module-level functions

- [ ] `_extract_mentions()` — L20 _(private)_

#### `app/services/notification_service.py` (5)

#### class `NotificationService`

- [ ] `NotificationService.list_for_user()` — L43
- [ ] `NotificationService.mark_read()` — L56
- [ ] `NotificationService.fan_out_mentions()` — L67

#### module-level functions

- [ ] `humanize_mention_preview()` — L18
- [ ] `_active_workspace_member_ids()` — L35 _(private)_

#### `app/services/notification_stream.py` (1)

#### module-level functions

- [ ] `notification_event_generator()` — L16

### Utils

#### `app/utils/notification_entity_label.py` (1)

#### module-level functions

- [ ] `resolve_notification_entity_label()` — L23

### DAOs

#### `app/dao/discussion.py` (3)

#### class `DiscussionDAO`

- [ ] `DiscussionDAO.get_by_entity()` — L8
- [ ] `DiscussionDAO.get_by_id()` — L31
- [ ] `DiscussionDAO.create()` — L38

#### `app/dao/notification.py` (3)

#### class `NotificationDAO`

- [ ] `NotificationDAO.get_for_user()` — L16
- [ ] `NotificationDAO.create()` — L48
- [ ] `NotificationDAO.mark_read()` — L87

## Calendar (15 callables)

### Services

#### `app/services/calendar_service.py` (15)

#### class `CalendarService` (BaseService)

- [ ] `CalendarService.get_events()` — L42
- [ ] `CalendarService._category_allowed()` — L75 _(private)_
- [ ] `CalendarService._expand_date_fields()` — L80 _(private)_
- [ ] `CalendarService._collect_work_orders()` — L118 _(private)_
- [ ] `CalendarService._collect_purchase_orders()` — L163 _(private)_
- [ ] `CalendarService._collect_expense_orders()` — L214 _(private)_
- [ ] `CalendarService._collect_sales_orders()` — L262 _(private)_
- [ ] `CalendarService._collect_sales_deliveries()` — L306 _(private)_
- [ ] `CalendarService._collect_invoices()` — L351 _(private)_
- [ ] `CalendarService._collect_invoice_payments()` — L401 _(private)_
- [ ] `CalendarService._collect_production_batches()` — L445 _(private)_
- [ ] `CalendarService._collect_projects()` — L483 _(private)_

#### module-level functions

- [ ] `_event_id()` — L25 _(private)_
- [ ] `_date_in_range()` — L29 _(private)_
- [ ] `_dt_to_date()` — L33 _(private)_

## Attachments & Uploads (122 callables)

### Managers

#### `app/managers/attachment_manager.py` (21)

#### class `AttachmentNotFoundError` (ValueError)

_(no methods defined in class body)_


#### class `AttachmentLimitError` (ValueError)

_(no methods defined in class body)_


#### class `AttachmentManager`

- [ ] `AttachmentManager.normalize_upload_request()` — L90
- [ ] `AttachmentManager.assert_entity_attachment_capacity()` — L93
- [ ] `AttachmentManager._upload_env()` — L113 _(private)_
- [ ] `AttachmentManager._is_production()` — L116 _(private)_
- [ ] `AttachmentManager.build_public_id()` — L119
- [ ] `AttachmentManager.build_asset_folder()` — L127
- [ ] `AttachmentManager.build_display_name()` — L141
- [ ] `AttachmentManager.resolve_entity_label()` — L149
- [ ] `AttachmentManager._fetch_entity_row()` — L175 _(private)_
- [ ] `AttachmentManager._extract_entity_label()` — L201 _(private)_
- [ ] `AttachmentManager._attachment_event_metadata()` — L230 _(private)_
- [ ] `AttachmentManager._append_attachment_ledger()` — L238 _(private)_
- [ ] `AttachmentManager._log_attachment_entity_events()` — L282 _(private)_
- [ ] `AttachmentManager.create_pending_attachment()` — L416
- [ ] `AttachmentManager.build_sign_response()` — L467
- [ ] `AttachmentManager.derive_urls()` — L504
- [ ] `AttachmentManager.build_pdf_page_image_url()` — L583
- [ ] `AttachmentManager.get_pdf_page_image()` — L622
- [ ] `AttachmentManager.to_response()` — L641
- [ ] `AttachmentManager.confirm_attachment()` — L680
- [ ] `AttachmentManager.delete_attachment()` — L775

#### `app/managers/attachment_markup_manager.py` (12)

#### class `AttachmentMarkupManager`

- [ ] `AttachmentMarkupManager._get_ready_attachment()` — L61 _(private)_
- [ ] `AttachmentMarkupManager._is_markupable()` — L95 _(private)_
- [ ] `AttachmentMarkupManager._resolve_user_name()` — L109 _(private)_
- [ ] `AttachmentMarkupManager._resolve_saved_stamp()` — L117 _(private)_
- [ ] `AttachmentMarkupManager._summarize_payload()` — L135 _(private)_
- [ ] `AttachmentMarkupManager._log_markup_event()` — L185 _(private)_
- [ ] `AttachmentMarkupManager._to_layer_response()` — L231 _(private)_
- [ ] `AttachmentMarkupManager._to_event_response()` — L265 _(private)_
- [ ] `AttachmentMarkupManager.list_layers()` — L303
- [ ] `AttachmentMarkupManager.list_events()` — L341
- [ ] `AttachmentMarkupManager.put_own_layer()` — L379
- [ ] `AttachmentMarkupManager.delete_own_layer()` — L509

#### `app/managers/mobile_upload_session_manager.py` (24)

#### class `MobileUploadSessionNotFoundError` (LookupError)

_(no methods defined in class body)_


#### class `MobileUploadSessionError` (ValueError)

_(no methods defined in class body)_


#### class `MobileUploadSessionManager`

- [ ] `MobileUploadSessionManager.__init__()` — L69 _(dunder)_
- [ ] `MobileUploadSessionManager._hash_token()` — L72 _(private)_
- [ ] `MobileUploadSessionManager._upload_env()` — L75 _(private)_
- [ ] `MobileUploadSessionManager._is_production()` — L78 _(private)_
- [ ] `MobileUploadSessionManager.build_staging_public_id()` — L81
- [ ] `MobileUploadSessionManager.build_staging_asset_folder()` — L88
- [ ] `MobileUploadSessionManager.create_session_token()` — L94
- [ ] `MobileUploadSessionManager.resolve_entity_label()` — L98
- [ ] `MobileUploadSessionManager.create_session()` — L116
- [ ] `MobileUploadSessionManager.to_create_response()` — L152
- [ ] `MobileUploadSessionManager._ensure_active()` — L164 _(private)_
- [ ] `MobileUploadSessionManager.get_by_raw_token()` — L176
- [ ] `MobileUploadSessionManager.get_for_creator()` — L183
- [ ] `MobileUploadSessionManager._staging_preview_url()` — L204 _(private)_
- [ ] `MobileUploadSessionManager.to_session_response()` — L224
- [ ] `MobileUploadSessionManager.to_public_response()` — L238
- [ ] `MobileUploadSessionManager.normalize_public_sign()` — L245
- [ ] `MobileUploadSessionManager.sign_staging_upload()` — L261
- [ ] `MobileUploadSessionManager.confirm_staging_upload()` — L330
- [ ] `MobileUploadSessionManager._destroy_staging_asset()` — L373 _(private)_
- [ ] `MobileUploadSessionManager.cancel_session()` — L385
- [ ] `MobileUploadSessionManager._promote_file_name()` — L395 _(private)_
- [ ] `MobileUploadSessionManager.promote_to_attachment()` — L405

#### module-level functions

- [ ] `_naive_utc()` — L51 _(private)_

### Services

#### `app/services/attachment_markup_service.py` (5)

#### class `AttachmentMarkupService` (BaseService)

- [ ] `AttachmentMarkupService.__init__()` — L22 _(dunder)_
- [ ] `AttachmentMarkupService.list_layers()` — L26
- [ ] `AttachmentMarkupService.list_events()` — L47
- [ ] `AttachmentMarkupService.put_own_layer()` — L68
- [ ] `AttachmentMarkupService.delete_own_layer()` — L93

#### `app/services/attachment_service.py` (7)

#### class `AttachmentService` (BaseService)

- [ ] `AttachmentService.__init__()` — L30 _(dunder)_
- [ ] `AttachmentService.sign_upload()` — L34
- [ ] `AttachmentService.confirm_upload()` — L79
- [ ] `AttachmentService.list_attachments()` — L103
- [ ] `AttachmentService.get_attachment()` — L136
- [ ] `AttachmentService.get_pdf_page_image()` — L150
- [ ] `AttachmentService.delete_attachment()` — L170

#### `app/services/mobile_upload_service.py` (8)

#### class `MobileUploadService` (BaseService)

- [ ] `MobileUploadService.__init__()` — L32 _(dunder)_
- [ ] `MobileUploadService.create_session()` — L36
- [ ] `MobileUploadService.get_session()` — L60
- [ ] `MobileUploadService.cancel_session()` — L76
- [ ] `MobileUploadService.promote_session()` — L98
- [ ] `MobileUploadService.get_public_session()` — L133
- [ ] `MobileUploadService.public_sign()` — L142
- [ ] `MobileUploadService.public_confirm()` — L169

### Utils

#### `app/utils/attachment_allowlist.py` (4)

#### class `AttachmentValidationError` (ValueError)

_(no methods defined in class body)_


#### class `AttachmentConfirmError` (ValueError)

_(no methods defined in class body)_


#### class `AttachmentTypeSpec`

_(no methods defined in class body)_


#### class `NormalizedUploadRequest`

_(no methods defined in class body)_


#### module-level functions

- [ ] `sanitize_file_name()` — L118
- [ ] `extract_extension()` — L127
- [ ] `normalize_upload_request()` — L137
- [ ] `validate_cloudinary_resource()` — L162

### Core

#### `app/core/cloudinary_client.py` (7)

#### class `CloudinaryNotConfiguredError` (RuntimeError)

_(no methods defined in class body)_


#### module-level functions

- [ ] `_ensure_configured()` — L18 _(private)_
- [ ] `generate_upload_signature()` — L34
- [ ] `build_signed_delivery_url()` — L54
- [ ] `get_resource()` — L82
- [ ] `destroy_resource()` — L97
- [ ] `rename_resource()` — L113
- [ ] `update_resource_metadata()` — L132

### DAOs

#### `app/dao/attachment.py` (5)

#### class `AttachmentDAO` (BaseDAO[Attachment, AttachmentCreateInternal, AttachmentUpdateInternal])

- [ ] `AttachmentDAO.get_active()` — L20
- [x] `AttachmentDAO.get_multi_active()` — L42 ~~[DELETED DEAD CODE]~~
- [x] `AttachmentDAO.get_by_uploader()` — L64 ~~[DELETED DEAD CODE]~~
- [ ] `AttachmentDAO.soft_delete()` — L88
- [ ] `AttachmentDAO.restore()` — L122

#### `app/dao/attachment_ledger.py` (1)

#### class `AttachmentLedgerDAO` (BaseDAO[AttachmentLedger, AttachmentLedgerCreate, AttachmentLedgerUpdate])

- [ ] `AttachmentLedgerDAO.get_by_workspace()` — L16

#### `app/dao/attachment_link.py` (6)

#### class `AttachmentLinkCreateSchema`

- [ ] `AttachmentLinkCreateSchema.__init__()` — L15 _(dunder)_
- [ ] `AttachmentLinkCreateSchema.model_dump()` — L30

#### class `AttachmentLinkDAO` (BaseDAO[AttachmentLink, AttachmentLinkCreateSchema, AttachmentLinkCreateSchema])

- [ ] `AttachmentLinkDAO.get_by_entity()` — L43
- [ ] `AttachmentLinkDAO.get_attachments_for_entity()` — L67
- [ ] `AttachmentLinkDAO.count_linked_attachments_for_entity()` — L96
- [ ] `AttachmentLinkDAO.get_links_for_attachment()` — L120

#### `app/dao/attachment_markup.py` (4)

#### class `AttachmentMarkupDAO` (BaseDAO[AttachmentMarkup, object, object])

- [ ] `AttachmentMarkupDAO.get_for_attachment()` — L13
- [ ] `AttachmentMarkupDAO.get_for_user()` — L30
- [ ] `AttachmentMarkupDAO.upsert_for_user()` — L48
- [ ] `AttachmentMarkupDAO.delete_for_user()` — L76

#### `app/dao/attachment_markup_event.py` (2)

#### class `AttachmentMarkupEventDAO` (BaseDAO[AttachmentMarkupEvent, object, object])

- [ ] `AttachmentMarkupEventDAO.list_for_attachment()` — L13
- [ ] `AttachmentMarkupEventDAO.create_event()` — L32

#### `app/dao/mobile_upload_session.py` (4)

#### class `MobileUploadSessionDAO` (BaseDAO[MobileUploadSession, dict, dict])

- [ ] `MobileUploadSessionDAO.get_by_token_hash()` — L22
- [ ] `MobileUploadSessionDAO.get_for_creator()` — L25
- [ ] `MobileUploadSessionDAO.mark_expired_if_needed()` — L43

#### module-level functions

- [ ] `_naive_utc()` — L12 _(private)_

#### `app/dao/project_attachment.py` (6)

#### class `ProjectAttachmentDAO` (BaseDAO[ProjectAttachment, ProjectAttachmentCreate, ProjectAttachmentResponse])

- [ ] `ProjectAttachmentDAO.get_by_project()` — L19
- [x] `ProjectAttachmentDAO.get_by_attachment()` — L46 ~~[DELETED DEAD CODE]~~
- [ ] `ProjectAttachmentDAO.get_link()` — L65
- [x] `ProjectAttachmentDAO.link_exists()` — L88 ~~[DELETED DEAD CODE]~~
- [x] `ProjectAttachmentDAO.unlink()` — L105 ~~[DELETED DEAD CODE]~~
- [x] `ProjectAttachmentDAO.get_attachment_count()` — L128 ~~[DELETED DEAD CODE]~~

#### `app/dao/project_component_attachment.py` (6)

#### class `ProjectComponentAttachmentDAO` (BaseDAO[ProjectComponentAttachment, ProjectComponentAttachmentCreate, ProjectComponentAttachmentResponse])

- [x] `ProjectComponentAttachmentDAO.get_by_project_component()` — L19 ~~[DELETED DEAD CODE]~~
- [x] `ProjectComponentAttachmentDAO.get_by_attachment()` — L47 ~~[DELETED DEAD CODE]~~
- [ ] `ProjectComponentAttachmentDAO.get_link()` — L66
- [x] `ProjectComponentAttachmentDAO.link_exists()` — L89 ~~[DELETED DEAD CODE]~~
- [x] `ProjectComponentAttachmentDAO.unlink()` — L106 ~~[DELETED DEAD CODE]~~
- [x] `ProjectComponentAttachmentDAO.get_attachment_count()` — L129 ~~[DELETED DEAD CODE]~~

## Help, Waitlist & Platform Admin (35 callables)

### Managers

#### `app/managers/help_ticket_manager.py` (10)

#### class `HelpTicketNotFoundError` (LookupError)

_(no methods defined in class body)_


#### class `HelpTicketForbiddenError` (PermissionError)

_(no methods defined in class body)_


#### class `HelpTicketManager`

- [ ] `HelpTicketManager.can_view_all_tickets()` — L34
- [ ] `HelpTicketManager.can_access_ticket()` — L38
- [ ] `HelpTicketManager.get_by_id_and_workspace()` — L50
- [ ] `HelpTicketManager.list_tickets()` — L68
- [ ] `HelpTicketManager.list_platform_tickets()` — L92
- [ ] `HelpTicketManager.get_platform_ticket()` — L111
- [ ] `HelpTicketManager.create_ticket()` — L123
- [ ] `HelpTicketManager.update_ticket()` — L138
- [ ] `HelpTicketManager.to_response()` — L165
- [ ] `HelpTicketManager._to_platform_item()` — L173 _(private)_

### Services

#### `app/services/help_ticket_service.py` (7)

#### class `HelpTicketService` (BaseService)

- [ ] `HelpTicketService.__init__()` — L27 _(dunder)_
- [ ] `HelpTicketService.create_ticket()` — L31
- [ ] `HelpTicketService.list_tickets()` — L56
- [ ] `HelpTicketService.get_ticket()` — L78
- [ ] `HelpTicketService.update_ticket()` — L96
- [ ] `HelpTicketService.list_platform_tickets()` — L127
- [ ] `HelpTicketService.get_platform_ticket()` — L144

#### `app/services/waitlist_service.py` (6)

#### class `WaitlistService` (BaseService)

- [ ] `WaitlistService.verify_turnstile()` — L39 _(async)_
- [ ] `WaitlistService.submit_signup()` — L68
- [ ] `WaitlistService.update_status()` — L104
- [ ] `WaitlistService.list_signups()` — L115

#### module-level functions

- [ ] `normalize_waitlist_email()` — L26
- [ ] `hash_client_ip()` — L30

### Core

#### `app/core/waitlist_admin.py` (1)

#### module-level functions

- [ ] `get_waitlist_admin()` — L9

### DAOs

#### `app/dao/help_ticket.py` (7)

#### class `DAOHelpTicket` (BaseDAO[HelpTicket, HelpTicketCreate, HelpTicketUpdate])

- [ ] `DAOHelpTicket.generate_ticket_number()` — L17
- [ ] `DAOHelpTicket.create_with_user()` — L32
- [ ] `DAOHelpTicket.get_by_id()` — L55
- [ ] `DAOHelpTicket.get_by_id_and_workspace()` — L68
- [ ] `DAOHelpTicket.list_by_workspace()` — L82
- [ ] `DAOHelpTicket.list_platform()` — L108
- [ ] `DAOHelpTicket.get_platform_by_id()` — L142

#### `app/dao/waitlist.py` (4)

#### class `WaitlistDAO` (BaseDAO[WaitlistSignup, WaitlistSignupRequest, WaitlistSignupRequest])

- [ ] `WaitlistDAO.get_by_email()` — L12
- [ ] `WaitlistDAO.list_signups()` — L15
- [ ] `WaitlistDAO.create_signup()` — L43
- [ ] `WaitlistDAO.update_status()` — L68

## Financial Audit (15 callables)

### Services

#### `app/services/financial_audit_log_service.py` (6)

#### class `FinancialAuditLogService`

- [ ] `FinancialAuditLogService.get_recent_logs()` — L10
- [ ] `FinancialAuditLogService.get_by_entity()` — L14
- [ ] `FinancialAuditLogService.get_related_logs()` — L18
- [ ] `FinancialAuditLogService.get_by_action_type()` — L22
- [ ] `FinancialAuditLogService.get_by_user()` — L26
- [ ] `FinancialAuditLogService.get_by_date_range()` — L30

### Utils

#### `app/utils/audit_logger.py` (3)

#### module-level functions

- [ ] `log_financial_audit()` — L14
- [ ] `create_change_dict()` — L110
- [ ] `extract_relevant_fields()` — L135

### DAOs

#### `app/dao/financial_audit_log.py` (6)

#### class `FinancialAuditLogCreate` (BaseModel)

_(no methods defined in class body)_


#### class `FinancialAuditLogDAO` (BaseDAO[FinancialAuditLog, FinancialAuditLogCreate, BaseModel])

- [ ] `FinancialAuditLogDAO.get_by_entity()` — L27
- [ ] `FinancialAuditLogDAO.get_related_logs()` — L64
- [ ] `FinancialAuditLogDAO.get_by_action_type()` — L114
- [ ] `FinancialAuditLogDAO.get_by_user()` — L148
- [ ] `FinancialAuditLogDAO.get_by_date_range()` — L182
- [ ] `FinancialAuditLogDAO.get_recent_logs()` — L219

## Shared Infrastructure (41 callables)

### Managers

#### `app/managers/base_manager.py` (1)

#### class `BaseManager` (Generic[ModelType])

- [ ] `BaseManager.__init__()` — L18 _(dunder)_

### Services

#### `app/services/base_service.py` (2)

#### class `BaseService`

- [ ] `BaseService._commit_transaction()` — L17 _(private)_
- [ ] `BaseService._rollback_transaction()` — L33 _(private)_

### Utils

#### `app/utils/datetime_serialize.py` (2)

#### module-level functions

- [ ] `serialize_utc_datetime()` — L14
- [ ] `ensure_utc_z_in_json()` — L28

#### `app/utils/time.py` (1)

#### module-level functions

- [ ] `utcnow()` — L15

### Core

#### `app/core/config.py` (2)

#### class `Settings` (BaseSettings)

- [ ] `Settings.assemble_cors_origins()` — L43
- [ ] `Settings.assemble_waitlist_admin_emails()` — L50

#### `app/core/deps.py` (5)

#### module-level functions

- [ ] `get_db()` — L19
- [ ] `get_current_user()` — L33
- [ ] `get_current_active_user()` — L80
- [ ] `get_current_workspace()` — L99
- [ ] `get_platform_admin()` — L160

#### `app/core/exceptions.py` (16)

#### class `APIException` (Exception)

- [ ] `APIException.__init__()` — L24 _(dunder)_

#### class `ValidationError` (APIException)

- [ ] `ValidationError.__init__()` — L44 _(dunder)_

#### class `AuthenticationError` (APIException)

- [ ] `AuthenticationError.__init__()` — L56 _(dunder)_

#### class `PermissionDeniedError` (APIException)

- [ ] `PermissionDeniedError.__init__()` — L67 _(dunder)_

#### class `NotFoundError` (APIException)

- [ ] `NotFoundError.__init__()` — L78 _(dunder)_

#### class `ConflictError` (APIException)

- [ ] `ConflictError.__init__()` — L89 _(dunder)_

#### class `BusinessRuleError` (APIException)

- [ ] `BusinessRuleError.__init__()` — L100 _(dunder)_

#### class `RateLimitError` (APIException) ~~[DELETED DEAD CODE]~~

- [ ] `RateLimitError.__init__()` — L112 _(dunder)_

#### class `InternalServerError` (APIException) ~~[DELETED DEAD CODE]~~

- [ ] `InternalServerError.__init__()` — L125 _(dunder)_

#### class `ServiceUnavailableError` (APIException) ~~[DELETED DEAD CODE]~~

- [ ] `ServiceUnavailableError.__init__()` — L136 _(dunder)_

#### module-level functions

- [ ] `api_exception_handler()` — L147 _(async)_
- [ ] `validation_exception_handler()` — L190 _(async)_
- [ ] `integrity_error_handler()` — L237 _(async)_
- [ ] `database_error_handler()` — L287 _(async)_
- [ ] `schema_error_handler()` — L318 _(async)_
- [ ] `generic_exception_handler()` — L354 _(async)_

#### `app/core/middleware.py` (2)

#### class `RequestContextMiddleware` (BaseHTTPMiddleware)

- [ ] `RequestContextMiddleware.dispatch()` — L22 _(async)_

#### class `SecurityHeadersMiddleware` (BaseHTTPMiddleware)

- [ ] `SecurityHeadersMiddleware.dispatch()` — L75 _(async)_

#### `app/core/utc_json_middleware.py` (1)

#### class `UtcJsonResponseMiddleware` (BaseHTTPMiddleware)

- [ ] `UtcJsonResponseMiddleware.dispatch()` — L17 _(async)_

### DAOs

#### `app/dao/base.py` (9)

#### class `BaseDAO` (Generic[ModelType, CreateSchemaType, UpdateSchemaType])

- [ ] `BaseDAO.__init__()` — L22 _(dunder)_
- [ ] `BaseDAO.get()` — L31
- [ ] `BaseDAO.get_multi()` — L44
- [ ] `BaseDAO.create()` — L60
- [ ] `BaseDAO.update()` — L85
- [ ] `BaseDAO.remove()` — L120
- [ ] `BaseDAO.get_by_workspace()` — L142
- [ ] `BaseDAO.get_by_id_and_workspace()` — L168
- [x] `BaseDAO.create_in_workspace()` — L195 ~~[DELETED DEAD CODE]~~

