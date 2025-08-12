-- =========================
-- Seed for routes, actions, and route_actions
-- =========================

-- ROUTES
INSERT INTO routes (id, route_name, description) VALUES
  (5,  'dashboard', 'Admin dashboard for displaying relevant data such as total employees that clocked in, sending messages, etc.'),
  (7,  'attendanceandtimetracking', 'Attendance and Time Tracking page'),
  (8,  'employeeengagement', 'Employee Engagement page'),
  (9,  'employeemanagement', 'Employee Management page'),
  (10, 'importdata', 'Import Data page'),
  (11, 'notificationsandcommunication', 'Notifications and Communication page'),
  (12, 'payrollandfinancialmanagement', 'Payroll and Financial Management page'),
  (13, 'performancemanagement', 'Performance Management page'),
  (14, 'profile', 'Profile page'),
  (15, 'reportandanalytics', 'Report and Analytics page'),
  (16, 'securityandcompliance', 'Security and Compliance page'),
  (17, 'systemadministration', 'System Administration page'),
  (18, 'traininganddevelopment', 'Training and Development page'),
  (19, 'verification', 'Admin & Route Verification page'),
  (20, 'workflowmanagement', 'Workflow Management page')
ON CONFLICT (id) DO NOTHING;

-- ACTIONS
INSERT INTO actions (action_name, description) VALUES
  -- Dashboard
  ('get_users_by_role', 'to be able to see users by role such as sending message in dashboard'),
  ('get_unread_messages', 'View unread messages on dashboard that display in notification icon'),
  ('mark_message_as_read', 'to be able to mark message to indicate that u have read it already'),
  ('get_message_inbox', 'view messages that are stored in inbox'),
  ('send_message', 'to be able to send messages to colleague'),
  ('dashboard', 'to be able to view dashboard datas such as total_employees, datas in charts,etc...'),
  ('reply_contact_request', 'reply to requests from users which is usually about changing password'),
  ('get_contact_requests', 'to be able to view requests from users that they send by using gmail'),

  -- Attendance and Time Tracking
  ('get_leave_request_details', 'admin can be able to let admin view the leave request details'),
  ('leave_requests_data', 'admin can be able to let admin sees leave requests from employees'),
  ('delete_shift_swap_request', 'admin can be able to delete shift related requests'),
  ('get_shift_swap_requests', 'admin can be able to view shift related requests from employees'),
('approve_shift_swap_request', 'admin can be able to approve shift related requests'),
('reject_shift_swap_request', 'admin can be able to disapprove shift related requests'),
  ('disapprove_attendance', 'admin can be able to disapprove attendance if the employee''s data don''t match the requirements (Ex: leave too early without permission)'),
  ('disapprove_overtime', 'admin can be able to disapprove employee''s overtime hours'),
  ('verify_overtime', 'admin can be able to verify employee''s overtime hours'),
  ('verify_attendance_admin', 'admin can be able to verify attendance that meet the company''s requirements (Ex: working enough hours)'),
  ('get_attendance_details', 'admin can be able to see the employee''s attendance details '),
  ('edit_attendance', 'admin can be able to update any attendance data'),
  ('delete_attendance', 'admin can be able to delete any employee''s attendance data'),
  ('assign_shift', 'admin can be able to assign shift for employee'),
  ('delete_assigned_shift', 'admin can be able to delete assigned shift for employee'),
  ('get_employee_shifts', 'admin can be able to see employee''s shift details display in the table'),
  ('get_shifts', 'admin can be able to see all shifts such as for choosing a specific shift to delete'),
  ('manage_leave', 'admin can be able to manage leave requests like approving,rejecting,etc...'),
  ('add_shift', 'admin can be able to add a new shift'),
  ('update_shift', 'admin can be able to update shift details'),
  ('delete_shift', 'admin can be able to deleted existed shifts'),
  ('attendanceandtimetracking_data', 'admin can be able to view employees in attendance logs table,view absent employees, view employees'' shifts'),
  ('delete_absent', 'admin can be able to delete employee''s attendance but only for absent status'),
  ('mark_absent', 'admin can be able to add employees into attendance logs when they don''t clock in and or clock out'),


  -- Employee Engagement
  ('view_teams', 'admin can be able to retrieve the team''s details such as for editing'),
  ('get_survey_assignments', 'admin can be able to see how many times employee participated in a specific survey'),
  ('allow_resubmission', 'admin can be able to let employee submits the assignments again'),
  ('get_travel_requests', 'admin can be able to see the travel requests that are requested by employees and also can be able to view the details of the requests'),
  ('approve_travel_request', 'admin can be able to approve the travel requests that are requested by employees'),
  ('reject_travel_request', 'admin can be able to reject the travel requests that are requested by employees'),
  ('get_health_resource_details', 'admin can be able to view the details for each health resources that are displayed inside the table structure'),
  ('delete_health_resource', 'admin can be able to delete health resources are displayed inside the table structure'),
  ('edit_health_resource', 'admin can be able to edit health resource details'),
  ('add_health_resource', 'admin can be able to add health resources for employees to learn about'),
  ('get_health_resources', 'admin can be able to see the created health resources display inside the table structure'),
  ('get_event_details', 'admin can be able to see events'' details'),
  ('update_event', 'admin can be able to update the details of the existed events that are displayed inside the table structure'),
  ('delete_event', 'admin can be able to delete the existed events that are displayed inside the table structure'),
  ('create_event', 'admin can be able to create new events for employees and admins to participate'),
  ('get_events', 'admin can be able to see the created events that are displayed inside the table structure'),
  ('get_survey_details', 'admin can be able to view the created survey''s details'),
  ('survey_responses', 'admin can be able to view the responses that are submitted by employees for any survey'),
  ('edit_survey', 'admin can be able to edit the created surveys that are displayed inside the table structure'),
  ('delete_survey', 'admin can be able to delete the created surveys that are displayed inside the table structure'),
  ('create_survey', 'admin can be able to create survey for employees to participate'),
  ('get_surveys', 'admin can be able to see the created surveys that are displayed inside the table structure'),
  ('delete_recognition', 'admin can be able to delete the details of the existed recognitions'),
  ('edit_recognition', 'admin can be able to edit the details of the existed recognitions'),
  ('add_recognition', 'admin can be able to add recognition for employees'),
  ('get_recognitions', 'admin can be able to see the existed recognitions'),
  ('delete_travel_request', 'admin can be able to delete the travel requests that are requested by employees'),

  -- Employee Management
  ('remove_team_member', 'admin can be able to remove team member from the existed team'),
  ('delete_team', 'admin can be able to delete the existed team'),
  ('add_team_member', 'admin can be able to add team member to the existed team'),
  ('edit_team', 'admin can be able to edit the existed teams'' details'),
  ('deactivate_employee', 'admin can be able to deactivate employee''s account so that they cannot login'),
  ('activate_employee', 'admin can be able to deactivate employee''s account so that they can login'),
  ('terminate_employee', 'admin can be able to terminate employee''s account so that they cannot login again but only for employees that leave the company permanently'),
  ('update_employee', 'admin can be able to be able to update all employee''s details'),
  ('create_team', 'admin can be able to be able to create a new team for employees'),
  ('get_team_management_data', 'admin can be able to be able to see the datas when creating a team such as list of employees so that u can pick which one to assign a team for'),
  ('add_employee', 'admin can be able add a new employee without them having to create their own account'),
  ('delete_employee', 'admin can be able delete employee''s account'),
  ('employeemanagement_data', 'admin can be able to see employee datas so that admin can manage them such as edit,view their details,activate their account,etc...'),

  -- Import Data
  ('import_employees', 'admin can be able to import employees using .csv file that has matching columns with existed database table and the right datatype too in order to import successfully'),

  -- Notifications and Communication
  ('feedback_request_responses', 'admin can be able to view responses of employees for feedback requests'),
  ('update_record', 'admin can be able to let admin update the records related to notificatiions and communications'),
  ('delete_record', 'admin can be able to let admin delete the records related to notificatiions and communications'),
  ('edit_record', 'admin can be able to populate the datas inside the edit modal when admin wants to update records related to notificatiions and communications'),
  ('notification_and_communication_data', 'admin can be able to let admin sees the datas related to notifications and communications such as the existed announcements,etc...'),
  ('create_feedback', 'admin can be able to let admin create feedback requests'),
  ('manage_alerts', 'admin can be able to let admin to create alerts'),
  ('create_announcement', 'admin can let admin to be able to create announcement'),
  ('create_meeting', 'admin can be able to let admin creates meetings'),

  -- Payroll and Financial Management
  ('get_savings_plan_request', 'admin can be able to see the details for a request of a savings plan'),
  ('delete_savings_plan_request', 'admin can be able to delete savings plan requests that are submitted by employees'),
  ('savings_plan_requests_for_plan', 'admin can be able to see each request''s details for a savings plan'),
  ('update_payment_status_not_yet_paid', 'admin can be able to update processed payrolls'' status to "not yet paid" '),
  ('update_payment_status_paid', 'admin can be able to update processed payrolls'' status to paid'),
  ('get_payrolls', 'admin can be able to see the processed payroll display inside the table structure'),
  ('delete_payroll', 'admin can be able to delete the processed payrolls that are displayed inside the table'),
  ('edit_payroll', 'admin can be able to edit the processed payrolls that are displayed inside the table'),
  ('view_payroll_details', 'admin can be able to let admin view the processed payroll details'),
  ('process_all_payroll', 'admin can be able to let admin processes reports for all employees such as for exporting as PDF'),
  ('process_payroll', 'admin can be able to let admin to process payroll per employee'),
  ('get_employee_details_salary', 'admin can be able to see the details of employee populate in the fields before processing salary for them and also be able to edit the details'),
  ('reject_expense', 'admin can be able to reject expense claims that are submitted from employees'),
  ('approve_expense', 'admin can be able to approve expense claims that are submitted from employees'),
  ('get_expense_claims', 'admin can be able to see expense claims that are submitted from employees'),
  ('delete_expense', 'admin can be able to delete expense claims that are submitted by employees'),
  ('generate_tax_document', 'admin can be able to let admin generate tax documents for employees'),
  ('get_tax_documents', 'admin can be able to let admin view the generated tax documents'),
  ('serve_tax_document', 'admin can be able to let admin view the details of the generated tax documents'),
  ('edit_tax_document', 'admin can be able to let admin edit the generated tax documents'),
  ('delete_tax_document', 'admin can be able to let admin delete the generated tax documents'),
  ('update_bonus', 'admin can be able to let admin update the bonuses that are displayed in the table structure'),
  ('get_all_bonuses', 'admin can be able to let admin view the bonuses that are displayed in the table structure'),
  ('add_bonus', 'admin can be able to let admin add bonus for employees'),
  ('delete_bonus', 'admin can be able to let admin delete the bonuses that are displayed in the table structure'),
  ('get_bonus', 'admin can be able to let admin view bonus details'),
  ('get_savings_plans', 'admin can be able to see all savings plan that are created'),
  ('get_saving_plan_details', 'admin can be able to view the savings plans'' details'),
  ('create_savings_plan', 'admin can be able to create new savings plan for employes'),
  ('get_all_employees', 'admin can be able to get all the employees such as for creating a new savings plan'),
  ('update_savings_plan', 'admin can be able to update existed savings plan'),
  ('delete_savings_plan', 'admin can be able to delete existed savings plan'),
  ('respond_savings_plan_request', 'admin can be able to respond to savings plan requests from employees'),

  -- Performance Management
  ('update_goal_evaluation', 'admin can be able to update evaluations on goals that are assigned to employees or teams'),
  ('get_team_goals', 'admin can be able to view goals that are assigned to teams'),
  ('update_progress', 'admin can be able to update goals'' progress for both that are assigned to employees or teams'),
  ('edit_note', 'admin can be able to edit the notes that are sent by employees related to the assigned goals'),
  ('delete_note', 'admin can be able to delete the notes that are sent by employees related to the assigned goals'),
  ('get_goal_evaluation', 'admin can be able to see the goal evaluation for the assigned goals for employees or teams'),
  ('delete_feedback', 'admin can be able to delete existed feedback for goals that are both assigned to employees or teams'),
  ('edit_feedback', 'admin can be able to edit existed feedback for goals that are both assigned to employees or teams'),
  ('submit_feedback', 'admin can be able to submit feedback for goals that are both assigned to employees or teams'),
  ('get_goals', 'admin can be able to view goals that are assigned to employees'),
  ('edit_review', 'admin can be able to edit the existed review of employee''s performance on projects or tasks'),
  ('delete_review', 'admin can be able to delete the existed review of employee''s performance on projects or tasks'),
  ('delete_goal', 'admin can be able to delete goals that are assigned for both employees and teams'),
  ('assign_goal', 'admin can be able to assign a goal to an employee or a team'),
  ('performance_data', 'admin can be able to see the details of the review of employee''s performance on projects or tasks'),
  ('submit_review', 'admin can be able to send a review of employee''s performance on projects or tasks'),
  ('get_tasks', 'admin can be able to see assigned tasks and its details'),
  ('get_employees', 'admin can be able to get employees datas such as for assigning task to them'),
  ('get_teams', 'admin can be able to get teams'' datas such as for assigning task to those teams'),
  ('assign_task', 'admin can be able to assign tasks or projects to employees and teams'),
  ('update_task', 'admin can be able to update existed tasks'' details'),
  ('delete_task', 'admin can be able to delete existed tasks'),
  ('delete_task_part', 'admin can be able to delete task part from existed tasks'),
  ('add_task_part', 'admin can be able to add task part to the existed tasks'),

  -- Profile
  ('admin_profile_picture', 'admin can be able to see your own profile'),
  ('get_profile_details', 'admin can be able to view profile details from dashboard'),
  ('update_profile_details', 'admin can be able to update profile details from dashboard'),

  -- Report and Analytics
  ('get_productivity_report', 'admin can be able to generate productivity report'),
  ('get_performance_report', 'admin can be able to generate performance report'),
  ('payroll_report', 'admin can be able to generate payroll report'),
  ('get_attendance_report', 'admin can be able to generate attendance report'),
  ('generate_reports', 'admin can be able to generate reports'),
  ('reporting_and_analytics_data', 'admin can be able to view the actions that are performed by admins such as logging in, edit details,etc...'),

  -- Security and Compliance
  ('search_incidents', 'admin can be able to search for specific incident log'),
  ('search_compliance', 'admin can be able to search for a specific log'),
  ('report_incident', 'admin can be able to report an incident'),
  ('display_incidents', 'admin can be able to see the incident logs'),
  ('display_compliance', 'admin can be able see all the audit logs'),
  ('view_incident', 'admin can be able to view incident logs'' details'),
  ('view_compliance', 'admin can be able to see the details of the log''s compliance'),
  ('delete_incident', 'admin can be able to delete incident logs'),
  ('delete_compliance', 'admin can be able to delete compliance logs'),
  ('edit_incident', 'admin can be able to edit incident logs'),
  ('edit_compliance', 'admin can be able to edit compliance logs'),
  ('get_document_categories', 'can be able to let admin see document categories such as for uploading documents or deleting existed categories'),
  ('get_document_history', 'admin can be able to view document history for each document'),
  ('delete_document', 'can let admin to delete the existed document'),
  ('edit_document', 'admin can be able to edit the existed document'),
  ('download_document', 'admin can be able to download documents that are displayed inside the table'),
  ('upload_document', 'admin can be able to upload documents'),
  ('delete_category', 'admin can be able to delete existed category but cannot delete category that is already used'),
  ('create_category', 'admin can be able to create new category in order for uploading new documents'),
  ('list_documents', 'admin can be able to see documents that are displayed in the table structure'),

  -- System Administration
  ('add_holiday', 'admin can be able to assign holidays for employees'),
  ('create_leave_balance', 'admin can be able to create leave balances for employees'),
  ('get_selection_data', 'admin can be able to see employees and select them such as for assigning a new holiday'),
  ('restore_backup', 'admins can be able to restore the database backup that they created'),
  ('list_backups', 'admin can be able to see the backups that are created'),
  ('create_backup', 'admin can be able to create a database backup so that they can use the old datas again'),
  ('delete_backup', 'admins can be able to delete database backup that they created'),
  ('get_leave_requests', 'admin can be able to see employee''s leave balances display inside the table structure'),
  ('get_holidays', 'admin can be able to see existed holidays that are displayed in the table structure'),
  ('view_leave_request', 'admin can be able to view leave requests'' details that are displayed inside the table structure'),
  ('edit_leave_request', 'admin can be able to edit leave requests'' details that are displayed inside the table structure'),
  ('delete_leave_request', 'admin can be able to delete leave requests'' details that are displayed inside the table structure'),
  ('delete_holiday', 'admin can be able to delete existed holiday'),
  ('edit_holiday', 'admin can be able to edit holiday details'),
  ('view_holiday', 'admin can be able to view holiday details'),
  ('edit_leave_balance', 'admin can be able to add or remove the amount of leave balances for employees'),
  ('get_employee_leave_details', 'admin can be able to view the details of employees'' leave balances'),
  ('get_leave_balances', 'admin can be able to see the leave balances for employees that are displayed inside the table structure'),
  ('download_backup', 'admin can be able to download the database backups that are created'),

  -- Training and Development
  ('remove_badge_assignment', 'admin can be able to remove the employee from a badge'),
  ('insert_module', 'admin can be able to add a new training module'),
  ('assign_assessment', 'Assign assessment'),
  ('issue_certificate', 'admin can be able to issue a certificate for employees'),
  ('get_assessment_details', 'admin can be able to view the assigned assessments'' details'),
  ('delete_certificate', 'admin can be able to delete the issued certificates that are displayed inside the table structure'),
  ('update_certificate', 'admin can be able to update the issued certificates that are displayed inside the table structure'),
  ('get_certificates', 'admin can be able to see the certificates that are displayed inside the table structure and also view its details'),
  ('get_modules', 'admin can be able to see the training modules that are displayed inside the table structure and also view its details'),
  ('update_module', 'admin can be able to update the training modules that are displayed inside the table structure'),
  ('delete_module', 'admin can be able to delete the training modules that are displayed inside the table structure'),
  ('update_assessment', 'admin can be able to update the assigned assessments that are displayed inside the table structure and also can be able to clear the score for the assigned assessments'),
  ('delete_assessment', 'admin can be able to delete the assigned assessments that are displayed inside the table structure'),
  ('get_assessments', 'admin can be able to see the assigned assessments that are displayed inside the table structure'),
  ('get_learning_resource_by_id', 'admin can be able to view the details of a specific learning resource'),
  ('get_all_learning_resources', 'admin can be able to see all the created learning resources inside the table structure'),
  ('add_learning_resource', 'admin can be able to add learning resources'),
  ('delete_learning_resource', 'admin can be able to delete the created learning resources that are displayed inside the table structure'),
  ('update_learning_resource', 'admin can be able to update the created learning resources that are displayed inside the table structure'),
  ('view_badge', 'admin can be able to view badge''s details'),
  ('delete_badge', 'admin can be able to delete badge''s details that are displayed inside the table structure'),
  ('update_badge', 'admin can be able to update badge''s details that are displayed inside the table structure'),
  ('add_badge', 'admin can be able to add badges to employees, Example : "Employee of the week"'),
  ('get_badges_with_assignments', 'admin can be able to see badges and the employees that are assigned to those badges'),
  ('assign_badge', 'admin can be able to assign badges to employees or teams'),
  ('get_assign_options', 'admin can be able to see the datas such as employees or teams in order to assign a badge for them'),

  -- Verification
  ('review_requests_action', 'admin can be able to approve or reject the requests that are made by other admins for access to actions for any pages'), 
  ('review_requests', 'admin can be able to see the requests that are made by other admins for access to actions for any pages'),
  ('reject_admin', 'admin can be able to verify the accounts that are registered'),
  ('verify_admin', 'admin can be able to verify the accounts that are registered'),
  ('get_pending_registrations', 'admin can be able to see the accounts that are '),
  ('delete_admin', 'admin can be able to delete the accounts that are registered'),
  ('remove_access', 'admin can be able to remove admin''s access from performing any actions that are related to any pages'),
  ('grant_access', 'admin can be able to grant access for admins to be able to perform actions on any pages like edit datas,deleting datas,etc...'),
  ('get_admins', 'admin can be able to see other admins so that they can grant or remove actions that they have accessed for pages '),
  ('get_admin_permissions', 'admin can be able to see the actions that admin already has accessed to and it will be pre-checked so that when you want to grant access for other admins , there''s no granting redundant action for the same page'),
  ('get_actions_for_route', 'admin can be able to see the actions for a specific page so that they can grant or remove access for other admins'),
  ('get_all_routes_and_actions', 'admin can be able to see all the pages and actions for each of those routes so that they can grant or remove access for other admins'),
  ('delete_action', 'admin can be able to delete the existed action that the page already had'),
  ('update_action', 'admin can be able to update the existed action that the page already had'),
  ('create_action', 'admin can be able to create an action for a page'),
  ('delete_route', 'admin can be able to delete the existed route'),
  ('update_route', 'admin can be able to update the existed route''s name'),
  ('create_route', 'admin can be able to create new route for a new page'),
  ('list_routes', 'admin can be able to see all the created routes'),

  -- Workflow Management
  ('view_timesheet', 'admin can be able to view the details of the generated timesheet'),
  ('get_my_requests', 'admin can be able to see the requests that they made to perform an action for a page'),
  ('get_all_routes_and_actions_to_request', 'admin can be able to see all the routes and actions for each of those routes so that admin can request to get access for actions to any page and also see the actions that they already have accessed to'),
  ('request_access', 'admin can be able to request access to any actions for any pages'),
  ('generate_timesheet', 'admin can be able to generate timesheet for employees'),
  ('get_employees_timesheet', 'admin can be able to see the generated employee''s timesheet'),
  ('get_timesheet_details', 'admin can be able to search for specific timesheet'),
  ('edit_timesheet', 'admin can be able to edit timesheet details'),
  ('delete_timesheet', 'admin can be able to delete the generated timesheet'),
  ('update_timesheet_status', 'admin can be able to approve or reject the employee''s generated timesheet '),
  ('delete_ticket', 'admin can be able to delete the submitted ticket'),
  ('edit_ticket', 'admin can be able to edit the submitted tickets'),
  ('get_tickets', 'admin can be able to see the tickets that are submitted by employees'),
  ('get_edit_ticket', 'admin can be to see the datas populate inside the edit modal so that they can edit the submitted tickets'),
  ('view_ticket', 'admin can be able to view the submitted tickets'' details'),
  ('respond_to_ticket', 'admin can be able to respond to the responses that are submitted by employees alongside the ticket itself')
ON CONFLICT (action_name) DO NOTHING;

-- ROUTE_ACTIONS
-- Dashboard (route_id = 5)
INSERT INTO route_actions (route_id, action_id) SELECT 5, id FROM actions WHERE action_name IN (
  'get_unread_messages','mark_message_as_read','get_message_inbox','send_message','dashboard','get_users_by_role','get_contact_requests','reply_contact_request'
);
-- Attendance and Time Tracking (route_id = 7)
INSERT INTO route_actions (route_id, action_id) SELECT 7, id FROM actions WHERE action_name IN (
  'disapprove_leaverequests','verify_leaverequests','disapprove_attendance','disapprove_overtime','verify_overtime','verify_attendance_admin','get_attendance_details','edit_attendance','delete_attendance','assign_shift','delete_assigned_shift','get_employee_shifts','get_shifts','manage_leave','add_shift','update_shift','delete_shift','attendanceandtimetracking_data','delete_absent','mark_absent','get_shift_swap_requests','approve_shift_swap_request','reject_shift_swap_request','delete_shift_swap_request','get_leave_request_details','leave_requests_data'
);
-- Employee Engagement (route_id = 8)
INSERT INTO route_actions (route_id, action_id) SELECT 8, id FROM actions WHERE action_name IN (
  'get_travel_requests','approve_travel_request','reject_travel_request','get_health_resource_details','delete_health_resource','edit_health_resource','add_health_resource','get_health_resources','get_event_details','update_event','delete_event','get_employees_by_role','create_event','get_events','get_survey_details','survey_responses','edit_survey','delete_survey','create_survey','get_surveys','delete_recognition','edit_recognition','add_recognition','get_recognitions','allow_resubmission','delete_travel_request','get_survey_assignments'
);
-- Employee Management (route_id = 9)
INSERT INTO route_actions (route_id, action_id) SELECT 9, id FROM actions WHERE action_name IN (
  'deactivate_employee','activate_employee','terminate_employee','update_employee','create_team','get_team_management_data','add_employee','delete_employee','employeemanagement_data','edit_team','add_team_member','delete_team','remove_team_member','view_teams'
);
-- Import Data (route_id = 10)
INSERT INTO route_actions (route_id, action_id) SELECT 10, id FROM actions WHERE action_name IN (
  'import_employees'
);
-- Notifications and Communication (route_id = 11)
INSERT INTO route_actions (route_id, action_id) SELECT 11, id FROM actions WHERE action_name IN (
  'update_record','delete_record','edit_record','notification_and_communication_data','create_feedback','manage_alerts','create_announcement','create_meeting','feedback_request_responses'
);
-- Payroll and Financial Management (route_id = 12)
INSERT INTO route_actions (route_id, action_id) SELECT 12, id FROM actions WHERE action_name IN (
  'process_all_payroll','process_payroll','get_employee_details_salary','reject_expense','approve_expense','get_expense_claims','delete_expense','generate_tax_document','get_tax_documents','serve_tax_document','edit_tax_document','delete_tax_document','update_bonus','get_all_bonuses','add_bonus','delete_bonus','get_bonus','get_savings_plans','get_saving_plan_details','create_savings_plan','get_all_employees','update_savings_plan','delete_savings_plan','respond_savings_plan_request','view_payroll_details','get_payrolls','update_payment_status_not_yet_paid','update_payment_status_paid','delete_payroll','delete_savings_plan_request','get_savings_plan_request','savings_plan_requests_for_plan','edit_payroll'
);
-- Performance Management (route_id = 13)
INSERT INTO route_actions (route_id, action_id) SELECT 13, id FROM actions WHERE action_name IN (
  'get_team_goals','update_progress','edit_note','delete_note','get_goal_evaluation','delete_feedback','edit_feedback','submit_feedback','get_goals','edit_review','delete_review','delete_goal','assign_goal','performance_data','submit_review','get_tasks','get_employees','get_teams','assign_task','update_task','delete_task','delete_task_part','add_task_part','update_goal_evaluation'
);
-- Profile (route_id = 14)
INSERT INTO route_actions (route_id, action_id) SELECT 14, id FROM actions WHERE action_name IN (
  'get_profile_details','update_profile_details','admin_profile_picture'
);
-- Report and Analytics (route_id = 15)
INSERT INTO route_actions (route_id, action_id) SELECT 15, id FROM actions WHERE action_name IN (
  'get_productivity_report','get_performance_report','payroll_report','get_attendance_report','generate_reports','reporting_and_analytics_data'
);
-- Security and Compliance (route_id = 16)
INSERT INTO route_actions (route_id, action_id) SELECT 16, id FROM actions WHERE action_name IN (
  'search_incidents','search_compliance','report_incident','display_incidents','display_compliance','view_incident','view_compliance','delete_incident','delete_compliance','edit_incident','edit_compliance','get_document_categories','get_document_history','delete_document','edit_document','download_document','upload_document','delete_category','create_category','list_documents'
);
-- System Administration (route_id = 17)
INSERT INTO route_actions (route_id, action_id) SELECT 17, id FROM actions WHERE action_name IN (
  'add_holiday','create_leave_balance','get_selection_data','restore_backup','list_backups','create_backup','delete_backup','get_leave_requests','get_holidays','view_leave_request','edit_leave_request','delete_leave_request','delete_holiday','edit_holiday','view_holiday','edit_leave_balance','get_employee_leave_details','get_leave_balances','download_backup'
);
-- Training and Development (route_id = 18)
INSERT INTO route_actions (route_id, action_id) SELECT 18, id FROM actions WHERE action_name IN (
  'insert_module','assign_assessment','issue_certificate','get_assessment_details','delete_certificate','update_certificate','get_certificates','get_modules','update_module','delete_module','update_assessment','delete_assessment','get_assessments','get_learning_resource_by_id','get_all_learning_resources','add_learning_resource','delete_learning_resource','update_learning_resource','view_badge','delete_badge','update_badge','add_badge','get_badges_with_assignments','assign_badge','get_assign_options','remove_badge_assignment'
);
-- Verification (route_id = 19)
INSERT INTO route_actions (route_id, action_id) SELECT 19, id FROM actions WHERE action_name IN (
  'reject_admin','verify_admin','get_pending_registrations','delete_admin','remove_access','grant_access','get_admins','get_admin_permissions','get_actions_for_route','get_all_routes_and_actions','delete_action','update_action','create_action','delete_route','update_route','create_route','list_routes','review_requests','review_requests_action'
);
-- Workflow Management (route_id = 20)
INSERT INTO route_actions (route_id, action_id) SELECT 20, id FROM actions WHERE action_name IN (
  'request_access','generate_timesheet','get_employees_timesheet','get_timesheet_details','edit_timesheet','delete_timesheet','update_timesheet_status','delete_ticket','edit_ticket','get_tickets','get_edit_ticket','view_ticket','respond_to_ticket','get_all_routes_and_actions_to_request','get_my_requests','view_timesheet');