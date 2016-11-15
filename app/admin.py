from copy import deepcopy

from django.forms import ModelForm, ValidationError
from django.utils.translation import ugettext_lazy as _
from django.contrib import admin

from app.models import *


class DisplayableAdminForm(ModelForm):
    def clean_content(form):
        status = form.cleaned_data.get("status")
        content = form.cleaned_data.get("content")
        if status == CONTENT_STATUS_PUBLISHED and not content:
            raise ValidationError(_("This field is required if status "
                                    "is set to published."))
        return content


class DisplayableAdmin(admin.ModelAdmin):
    """
    Admin class for subclasses of the abstract ``Displayable`` model.
    """

    list_display = ("title", "status",)
    list_display_links = ("title",)
    list_editable = ("status",)
    list_filter = ("status",)
    # modeltranslation breaks date hierarchy links, see:
    # https://github.com/deschler/django-modeltranslation/issues/324
    # Once that's resolved we can restore this.
    date_hierarchy = "publish_date"
    radio_fields = {"status": admin.HORIZONTAL}
    fieldsets = (
        (None, {
            "fields": ["title", "status", ("publish_date", "expiry_date")],
        }),
        (_("Meta data"), {
            "fields": ["_meta_title", "slug",
                       ("description", "gen_description"),
                       "keywords"],
            "classes": ("collapse-closed",)
        }),
    )

    form = DisplayableAdminForm

    def __init__(self, *args, **kwargs):
        super(DisplayableAdmin, self).__init__(*args, **kwargs)
        try:
            self.search_fields = list(set(list(self.search_fields) + list(
                self.model.objects.get_search_fields().keys())))
        except AttributeError:
            pass

    def check_permission(self, request, page, permission):
        """
        Subclasses can define a custom permission check and raise an exception
        if False.
        """
        pass

    def save_model(self, request, obj, form, change):
        """
        Save model for every language so that field auto-population
        is done for every each of it.
        """
        super(DisplayableAdmin, self).save_model(request, obj, form, change)


class OwnableAdmin(admin.ModelAdmin):
    """
    Admin class for models that subclass the abstract ``Ownable``
    model. Handles limiting the change list to objects owned by the
    logged in user, as well as setting the owner of newly created
    objects to the logged in user.

    Remember that this will include the ``user`` field in the required
    fields for the admin change form which may not be desirable. The
    best approach to solve this is to define a ``fieldsets`` attribute
    that excludes the ``user`` field or simple add ``user`` to your
    admin excludes: ``exclude = ('user',)``
    """

    def save_form(self, request, form, change):
        """
        Set the object's owner as the logged in user.
        """
        obj = form.save(commit=False)
        if obj.user_id is None:
            obj.user = request.user
        return super(OwnableAdmin, self).save_form(request, form, change)

    def get_queryset(self, request):
        """
        Filter the change list by currently logged in user if not a
        superuser. We also skip filtering if the model for this admin
        class has been added to the sequence in the setting
        ``OWNABLE_MODELS_ALL_EDITABLE``, which contains models in the
        format ``app_label.object_name``, and allows models subclassing
        ``Ownable`` to be excluded from filtering, eg: ownership should
        not imply permission to edit.
        """
        qs = super(OwnableAdmin, self).get_queryset(request)
        return qs.filter(user__id=request.user.id)


class FeaturedImageInline(admin.TabularInline):
    model = FeaturedImage


class MessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'created_at')


blogpost_fieldsets = deepcopy(DisplayableAdmin.fieldsets)
blogpost_fieldsets[0][1]["fields"].insert(1, "categories")
blogpost_fieldsets[0][1]["fields"].extend(["content"])
blogpost_list_display = ["title", "user", "status"]
blogpost_fieldsets = list(blogpost_fieldsets)
blogpost_fieldsets.insert(1, (_("Other posts"), {
    "classes": ("collapse-closed",),
    "fields": ("related_posts",)}))
blogpost_list_filter = deepcopy(DisplayableAdmin.list_filter) + ("categories",)


class BlogPostAdmin(DisplayableAdmin, OwnableAdmin):
    """
    Admin class for blog posts.
    """

    fieldsets = blogpost_fieldsets
    inlines = [FeaturedImageInline, ]
    list_display = blogpost_list_display
    list_filter = blogpost_list_filter
    filter_horizontal = ("categories", "related_posts",)

    def save_form(self, request, form, change):
        """
        Super class ordering is important here - user must get saved first.
        """
        OwnableAdmin.save_form(self, request, form, change)
        return DisplayableAdmin.save_form(self, request, form, change)


class KeywordAdmin(admin.ModelAdmin):
    list_display = ("title",)
    fieldsets = ((None, {"fields": ("title",)}),)

    # def get_model_perms(self, request):
    #     ## check if the request.user should see model, if not:
    #     return {'change': False, 'add': True, 'list': False}


class BlogCategoryAdmin(admin.ModelAdmin):
    """
    Admin class for blog categories. Hides itself from the admin menu
    unless explicitly specified.
    """

    fieldsets = ((None, {"fields": ("title",)}),)


admin.site.register(Message, MessageAdmin)
admin.site.register(Keyword, KeywordAdmin)
admin.site.register(FeaturedImage)
admin.site.register(BlogPost, BlogPostAdmin)
admin.site.register(BlogCategory, BlogCategoryAdmin)
