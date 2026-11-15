from routes.appointments import appointments_bp
from routes.auth import auth_bp
from routes.bhw import bhw_bp
from routes.consultations import consultations_bp
from routes.core import core_bp
from routes.inventory import inventory_bp
from routes.maternal import maternal_bp
from routes.patients import patients_bp
from routes.reports import reports_bp


def register_blueprints(app) -> None:
	app.register_blueprint(appointments_bp)
	app.register_blueprint(auth_bp)
	app.register_blueprint(bhw_bp)
	app.register_blueprint(consultations_bp)
	app.register_blueprint(core_bp)
	app.register_blueprint(inventory_bp)
	app.register_blueprint(maternal_bp)
	app.register_blueprint(patients_bp)
	app.register_blueprint(reports_bp)


def register_legacy_endpoint_aliases(app) -> None:
	alias_specs = [
		('/midwife_dashboard', 'midwife_dashboard', 'maternal.midwife_dashboard', ['GET']),
		('/prenatal_tracker', 'prenatal_tracker', 'maternal.prenatal_tracker', ['GET']),
		('/prenatal/enroll', 'enroll_prenatal', 'maternal.enroll_prenatal', ['POST']),
		('/mark_delivered/<int:record_id>', 'mark_delivered', 'maternal.mark_delivered', ['POST']),
		('/immunization_schedule', 'immunization_schedule', 'maternal.immunization_schedule', ['GET', 'POST']),
		('/immunization/<int:schedule_id>/complete', 'complete_immunization', 'maternal.complete_immunization', ['POST']),
		('/immunization/<int:schedule_id>/delete', 'delete_immunization', 'maternal.delete_immunization', ['POST']),
		('/immunization/<int:schedule_id>/notify', 'notify_immunization', 'maternal.notify_immunization', ['POST']),
		('/api/prenatal_stats', 'prenatal_stats', 'maternal.prenatal_stats', ['GET']),
		('/bhw_dashboard', 'bhw_dashboard', 'bhw.bhw_dashboard', ['GET']),
		('/household-profile', 'household_profile', 'bhw.household_profile', ['GET', 'POST']),
		('/operation-timbang', 'operation_timbang', 'bhw.operation_timbang', ['GET', 'POST']),
		('/operation-timbang/history/<int:patient_id>', 'operation_timbang_history', 'bhw.operation_timbang_history', ['GET']),
	]

	for rule, legacy_endpoint, target_endpoint, methods in alias_specs:
		app.add_url_rule(rule, endpoint=legacy_endpoint, view_func=app.view_functions[target_endpoint], methods=methods)
