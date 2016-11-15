"""djangoboiler URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.9/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url, include
from django.contrib import admin
from django.contrib.auth import views as auth_views

from app import views

# TODO: Definir url para contato, DATA, view_data, submit_email_notification_list
urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^admin/login/$', auth_views.login),
    url(r'^ckeditor/', include('ckeditor_uploader.urls')),
    url(r'^$', views.home_paginate, name='index'),
    url(r'^category/(?P<slug>[^\.]+)', views.list_category_paginate, name='category'),
    url(r'^sub-category/(?P<slug>[^\.]+)', views.list_subcategory_paginate, name='sub-category'),
    url(r'^post/(?P<slug>[^\.]+)', views.view_post, name='view_post'),
    url(r'^data/$', views.data, name='data'),
    url(r'^data/(?P<id>[^\.]+)', views.view_data, name='view_data'),
    url(r'^search/$', views.search_paginate, name='search'),
    url(r'^team/$', views.team, name='team'),
    url(r'^contact', views.contact, name='contact'),
    url(r'^submit-contact', views.submit_message, name='submit_contact'),
    url(r'^submit-news', views.submit_mail_newsletter, name='mail_newsletter'),
]
