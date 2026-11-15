SHOW TABLES;

SELECT COUNT(*) AS patients FROM patient;
SELECT COUNT(*) AS consultations FROM consultation;
SELECT COUNT(*) AS appointments FROM appointment;
SELECT COUNT(*) AS notifications FROM notification;

SELECT p.full_name, a.appointment_date, a.appointment_time, a.status
FROM appointment a
JOIN patient p ON p.id = a.patient_id
ORDER BY a.id DESC
LIMIT 5;

SELECT c.id, p.full_name, c.consultation_type, c.diagnosis
FROM consultation c
JOIN patient p ON p.id = c.patient_id
ORDER BY c.id DESC
LIMIT 5;