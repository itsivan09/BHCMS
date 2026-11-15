# Barangay Health Center Management System (BHCMS) - Features

## 1. Non-Technical Feature List

1. Secure user login and logout.
2. Different dashboards for health staff roles.
3. Patient registration and patient profile management.
4. Editing and deleting patient records.
5. Patient search and quick lookup.
6. Consultation recording with vital signs and notes.
7. Medicine dispensing during consultations.
8. Consultation history viewing per patient.
9. Patient record export (PDF format).
10. Appointment booking and schedule viewing.
11. Appointment conflict checking (avoid double-booking).
12. Appointment cancellation and completion tracking.
13. Email support for appointment confirmations/reminders.
14. Inventory tracking for medicines and supplies.
15. Low-stock and expiry monitoring.
16. Prenatal enrollment and pregnancy monitoring.
17. Delivery status marking (close prenatal case).
18. Immunization scheduling and completion tracking.
19. Child nutrition monitoring (Operation Timbang/BMI status).
20. Household profiling and community-level monitoring.
21. Community events recording with optional image upload.
22. Notifications center (alerts and updates).
23. Reports dashboard (morbidity and demographics).
24. Data export to CSV and Excel for patients and inventory.

## 2. Role-Based Feature Access

### Admin

1. Full access to all modules.
2. Can view all dashboards and records.
3. Can manage patients, consultations, appointments, inventory, and reports.
4. Can access maternal, prenatal, and immunization tools.
5. Can delete restricted records/items where role checks apply.
6. Can use report/export endpoints and notification tools.
7. Can run appointment test email feature.

### Midwife

1. Access to midwife dashboard and maternal care modules.
2. Can manage prenatal tracker and immunization schedules.
3. Can create, edit, and delete consultations (including medicine entries).
4. Can view and manage appointments (including status updates).
5. Can access reports and exports.
6. Can manage inventory (including restricted delete actions).
7. Can delete patients (per route restrictions).

### BHW

1. Access to BHW dashboard, household profiling, and Operation Timbang.
2. Can register/manage patients and add consultations.
3. Can book, check, cancel, and complete appointments within allowed rules.
4. Can view inventory page and add items.
5. Can record community events.
6. Cannot access Admin/Midwife-only reporting APIs and maternal-only functions.
7. Cannot perform actions explicitly restricted to Admin/Midwife (for example some delete, edit, and reporting operations).

## 3. Notes

1. Access permissions are enforced by role checks in backend routes.
2. Some flows include automatic notifications and email reminders when enabled in configuration.
3. Feature availability in the UI depends on both role permissions and current data state.
