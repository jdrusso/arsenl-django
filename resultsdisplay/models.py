from django.db import models
from django.utils import timezone
import datetime

class TestCase(models.Model):

    #Should this be an AutoField?
    test_case_id = models.IntegerField(primary_key=True)

    name = models.TextField()
    test_function = models.TextField()
    test_type = models.TextField()
    class Meta:
        managed = False
        db_table = 'test_case'

    def __unicode__(self):
        return self.name


class Project(models.Model):

    #Should this be an AutoField?
    project_id = models.IntegerField(primary_key=True)

    name = models.TextField()
    repo_list = models.TextField()
    class Meta:
        managed = False
        db_table = 'project'

    def __unicode__(self):
        return self.name

class TestResult(models.Model):

    #Should this be an AutoField?
    test_result_id = models.IntegerField(primary_key=True)

    datestamp = models.TextField()
    run_num = models.IntegerField()
    run_time = models.TextField()
    result = models.TextField()
    test_case = models.ForeignKey(TestCase, db_column='test_case_id')
    project = models.ForeignKey(Project, db_column='project_id')
    sha_list = models.TextField()
    xml_path = models.TextField()
    class Meta:
        managed = False
        db_table = 'test_result'

    def __unicode__(self):
        return self.test_result_id