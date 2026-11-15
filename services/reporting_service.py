from datetime import date, datetime, timedelta


def build_morbidity_payload(consultations):
    diagnosis_counts = {}
    for consultation in consultations:
        diagnosis_counts[consultation.diagnosis] = diagnosis_counts.get(consultation.diagnosis, 0) + 1

    sorted_counts = sorted(diagnosis_counts.items(), key=lambda item: item[1], reverse=True)
    top_items = sorted_counts[:10]

    return {
        'labels': [diagnosis[:30] for diagnosis, _ in top_items],
        'datasets': [{
            'label': 'Diagnosis Frequency (Last 30 Days)',
            'data': [count for _, count in top_items],
            'backgroundColor': '#0e7c86',
            'borderColor': '#0a5f67',
            'borderWidth': 1,
        }],
        'total_consultations': len(consultations),
        'total_unique_diagnoses': len(diagnosis_counts),
    }


def _calculate_age(birth_date, today):
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def build_demographic_payload(patients, pregnant_patients_count):
    age_groups = {'0-5': 0, '6-12': 0, '13-18': 0, '19-35': 0, '36-50': 0, '50+': 0}
    gender_counts = {'Male': 0, 'Female': 0, 'Other': 0}
    purok_counts = {}

    today = date.today()
    for patient in patients:
        age = _calculate_age(patient.birth_date, today)

        if age <= 5:
            age_groups['0-5'] += 1
        elif age <= 12:
            age_groups['6-12'] += 1
        elif age <= 18:
            age_groups['13-18'] += 1
        elif age <= 35:
            age_groups['19-35'] += 1
        elif age <= 50:
            age_groups['36-50'] += 1
        else:
            age_groups['50+'] += 1

        if patient.gender in gender_counts:
            gender_counts[patient.gender] += 1

        purok_counts[patient.purok] = purok_counts.get(patient.purok, 0) + 1

    return {
        'total_patients': len(patients),
        'age_distribution': age_groups,
        'gender_distribution': gender_counts,
        'purok_distribution': purok_counts,
        'pregnant_patients': pregnant_patients_count,
    }
