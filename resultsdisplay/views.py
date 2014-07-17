from django.shortcuts import render
from django.views import generic
from resultsdisplay.models import TestResult, TestCase, Project

group_id = {'Unit' : 0, 'Regression' : 1}
group_name = {0 : 'Unit', 1 : 'Regression'}

class IndexView(generic.ListView):

	template_name = 'resultsdisplay/index.html'
	context_object_name = 'project_list'

	def get_queryset(self):
		"""Return all the current projects."""
		return Project.objects.order_by('project_id')

class TestRunView(generic.ListView):

	pk_url_kwarg = 'run_pk'

	template_name = 'resultsdisplay/TestRun.html'
	context_object_name = 'testrun_list'

	def get_queryset(self):
		return TestResult.objects.values().distinct('run_num')[::-1]

class TestGroupView(generic.ListView):

	pk_url_kwarg = 'run_pk'

	template_name = 'resultsdisplay/TestGroup.html'
	context_object_name = 'testgroup_list'

	def get_queryset(self):
		"""Return all the current test groups."""
		return TestCase.objects.values().distinct('test_type')

	def get_context_data(self, **kwargs):
		context = super(TestGroupView, self).get_context_data(**kwargs)
		context['run_num'] = int(self.kwargs['run_num'])
		context['project_id'] = int(self.kwargs['project_pk'])

		for group in context['testgroup_list']:

			group['type_num'] = group_id[group['test_type']]
		return context

class TestCaseView(generic.ListView):

	pk_url_kwarg = 'group_pk'

	template_name = 'resultsdisplay/TestCase.html'
	context_object_name = 'testcase_list'

	def get_queryset(self):
		"""Return all the current test cases"""
		#return TestCase.objects.values()

		this_type_id = int(self.kwargs['group_id'])
		this_type_name = group_name[this_type_id]

		type_id = {}

		for case in TestCase.objects.values():
			type_id[case['test_case_id']] = case['test_type']

		valid_ids = [x for x in type_id if type_id[x] == this_type_name]

		return TestResult.objects.extra(where=["run_num = %s", "test_case_id BETWEEN %s and %s"], 
			params=[int(self.kwargs['run_num']),  min(valid_ids), max(valid_ids)])

	def get_context_data(self, **kwargs):
		context = super(TestCaseView, self).get_context_data(**kwargs)
		context['project_id'] = int(self.kwargs['project_pk'])
		context['group_id'] = int(self.kwargs['group_id'])

		for case in context['testcase_list']:

			case.name = TestCase.objects.extra(where=['test_case_id=%s'],
			 	params=[case.test_case_id])[0]

			case.type = TestCase.objects.filter(test_case_id__exact=case.test_case_id).values()[0]['test_type']

			#case.type = 'Unit' or 'Regression', group_id = 0, 1
			#if not group_id[case.type] == context['group_id']:
			#	case.delete()

		return context

class TestResultView(generic.DetailView):

	template_name = 'resultsdisplay/TestResult.html'
	context_object_name = 'testresult'

	def get_queryset(self):
		"""Return all the current test cases"""
		return TestResult.objects.values()

	def get_context_data(self, **kwargs):
		context = super(TestResultView, self).get_context_data(**kwargs)

		context['testresult']['name'] = TestCase.objects.extra(where=['test_case_id=%s'], params=[context['testresult']['test_case_id']])[0]
		#context['testresult']['name'] = self.kwargs['pk']
		return context


#class TestResultView(generic.DetailView):