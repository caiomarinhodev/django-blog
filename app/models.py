from __future__ import unicode_literals

from django.apps import apps

from mezzanine.utils.html import TagCloser
from mezzanine.utils.urls import unique_slug
from mezzanine.utils.models import base_concrete_model

try:
    from urllib.parse import urljoin
except ImportError:  # Python 2
    from urlparse import urljoin

from django.core.urlresolvers import reverse

from cloudinary.models import CloudinaryField
from django.contrib.auth.models import User
from django.db.models import permalink
from django.template.defaultfilters import slugify
from future.builtins import str
from ckeditor.fields import RichTextField

from ckeditor_uploader.fields import RichTextUploadingField

try:
    from urllib.request import urlopen
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlopen, urlencode

from django.db import models
from django.template.defaultfilters import truncatewords_html
from django.utils.html import strip_tags
from django.utils.timesince import timesince
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

SELF_CLOSING_TAGS = ['br', 'img']


class Slugged(models.Model):
    """
    Abstract model that handles auto-generating slugs. Each slugged
    object is also affiliated with a specific site object.
    """

    title = models.CharField(_("Title"), max_length=500)
    slug = models.CharField(_("URL"), max_length=2000, blank=True, null=True,
                            help_text=_("Leave blank to have the URL auto-generated from "
                                        "the title."))

    class Meta:
        abstract = True

    def __unicode__(self):
        return self.title

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """
        If no slug is provided, generates one before saving.
        """
        if not self.slug:
            self.slug = self.generate_unique_slug()
        super(Slugged, self).save(*args, **kwargs)

    def generate_unique_slug(self):
        """
        Create a unique slug by passing the result of get_slug() to
        utils.urls.unique_slug, which appends an index if necessary.
        """
        # For custom content types, use the ``Page`` instance for
        # slug lookup.
        concrete_model = base_concrete_model(Slugged, self)
        slug_qs = concrete_model.objects.exclude(id=self.id)
        return unique_slug(slug_qs, "slug", self.get_slug())

    def get_slug(self):
        """
        Allows subclasses to implement their own slug creation logic.
        """
        attr = "title"
        # Get self.title_xx where xx is the default language, if any.
        # Get self.title otherwise.
        return slugify(getattr(self, attr, None) or self.title)


class Keyword(Slugged):
    class Meta:
        verbose_name = _("Keyword")
        verbose_name_plural = _("Keywords")


class MetaData(models.Model):
    """
    Abstract model that provides meta data for content.
    """

    _meta_title = models.CharField(_("Title"), null=True, blank=True,
                                   max_length=500,
                                   help_text=_("Optional title to be used in the HTML title tag. "
                                               "If left blank, the main title field will be used."))
    description = models.TextField(_("Description"), blank=True)
    gen_description = models.BooleanField(_("Generate description"),
                                          help_text=_("If checked, the description will be automatically "
                                                      "generated from content. Uncheck if you want to manually "
                                                      "set a custom description."), default=True)
    keywords = models.ManyToManyField(Keyword, verbose_name=_("Keywords"))

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """
        Set the description field on save.
        """
        if self.gen_description:
            self.description = strip_tags(self.description_from_content())
        super(MetaData, self).save(*args, **kwargs)

    def meta_title(self):
        """
        Accessor for the optional ``_meta_title`` field, which returns
        the string version of the instance if not provided.
        """
        return self._meta_title or getattr(self, "title", str(self))

    def description_from_content(self):
        """
        Returns the first block or sentence of the first content-like
        field.
        """
        description = ""
        # Fall back to the title if description couldn't be determined.
        if not description:
            description = str(strip_tags(self.content))
        # Strip everything after the first block or sentence.
        ends = ("</p>", "<br />", "<br/>", "<br>", "</ul>",
                "\n", ". ", "! ", "? ")
        for end in ends:
            pos = description.lower().find(end)
            if pos > -1:
                description = TagCloser(description[:pos]).html
                break
        else:
            description = truncatewords_html(description, 150)
        try:
            description = unicode(description)
        except NameError:
            pass  # Python 3.
        return description


class TimeStamped(models.Model):
    """
    Provides created and updated timestamps on models.
    """

    class Meta:
        abstract = True

    created = models.DateTimeField(null=True, editable=False)
    updated = models.DateTimeField(null=True, editable=False)

    def save(self, *args, **kwargs):
        _now = now()
        self.updated = _now
        if not self.id:
            self.created = _now
        super(TimeStamped, self).save(*args, **kwargs)


CONTENT_STATUS_DRAFT = False
CONTENT_STATUS_PUBLISHED = True
CONTENT_STATUS_CHOICES = (
    (CONTENT_STATUS_DRAFT, _("Draft")),
    (CONTENT_STATUS_PUBLISHED, _("Published")),
)

SHORT_URL_UNSET = "unset"


class Displayable(Slugged, MetaData, TimeStamped):
    """
    Abstract model that provides features of a visible page on the
    website such as publishing fields. Basis of Mezzanine pages,
    blog posts, and Cartridge products.
    """

    status = models.BooleanField(_("Status"),
                                 choices=CONTENT_STATUS_CHOICES, default=CONTENT_STATUS_PUBLISHED,
                                 help_text=_("With Draft chosen, will only be shown for admin users "
                                             "on the site."))
    publish_date = models.DateTimeField(_("Published from"),
                                        help_text=_("With Published chosen, won't be shown until this time"),
                                        blank=True, null=True, db_index=True)
    expiry_date = models.DateTimeField(_("Expires on"),
                                       help_text=_("With Published chosen, won't be shown after this time"),
                                       blank=True, null=True)
    short_url = models.URLField(blank=True, null=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """
        Set default for ``publish_date``. We can't use ``auto_now_add`` on
        the field as it will be blank when a blog post is created from
        the quick blog form in the admin dashboard.
        """
        if self.publish_date is None:
            self.publish_date = now()
        super(Displayable, self).save(*args, **kwargs)

    def publish_date_since(self):
        """
        Returns the time since ``publish_date``.
        """
        return timesince(self.publish_date)

    publish_date_since.short_description = _("Published from")

    def get_absolute_url(self):
        """
        Raise an error if called on a subclass without
        ``get_absolute_url`` defined, to ensure all search results
        contains a URL.
        """
        name = self.__class__.__name__
        raise NotImplementedError("The model %s does not have "
                                  "get_absolute_url defined" % name)


class RichText(models.Model):
    """
    Provides a Rich Text field for managing general content and making
    it searchable.
    """

    content = RichTextUploadingField(_("Content"))

    class Meta:
        abstract = True


class Ownable(models.Model):
    """
    Abstract model that provides ownership of an object for a user.
    """

    user = models.ForeignKey(User, verbose_name=_("Author"),
                             related_name="%(class)ss")

    class Meta:
        abstract = True

    def is_editable(self, request):
        """
        Restrict in-line editing to the objects's owner and superusers.
        """
        return request.user.is_superuser or request.user.id == self.user_id


class ContentTyped(models.Model):
    """
    Mixin for models that can be subclassed to create custom types.
    In order to use them:

    - Inherit model from ContentTyped.
    - Call the set_content_model() method in the model's save() method.
    - Inherit that model's ModelAdmin from ContentTypesAdmin.
    - Include "admin/includes/content_typed_change_list.html" in the
    change_list.html template.
    """
    content_model = models.CharField(editable=False, max_length=50, null=True)

    class Meta:
        abstract = True

    @classmethod
    def get_content_model_name(cls):
        """
        Return the name of the OneToOneField django automatically creates for
        child classes in multi-table inheritance.
        """
        return cls._meta.object_name.lower()

    @classmethod
    def get_content_models(cls):
        """ Return all subclasses of the concrete model.  """
        concrete_model = base_concrete_model(ContentTyped, cls)
        return [m for m in apps.get_models()
                if m is not concrete_model and issubclass(m, concrete_model)]

    def set_content_model(self):
        """
        Set content_model to the child class's related name, or None if this is
        the base class.
        """
        if not self.content_model:
            is_base_class = (
                base_concrete_model(ContentTyped, self) == self.__class__)
            self.content_model = (
                None if is_base_class else self.get_content_model_name())

    def get_content_model(self):
        """
        Return content model, or if this is the base class return it.
        """
        return (getattr(self, self.content_model) if self.content_model
                else self)


class BlogCategory(Slugged):
    """
    A category for grouping blog posts into a series.
    """

    class Meta:
        verbose_name = _("Blog Category")
        verbose_name_plural = _("Blog Categories")
        ordering = ("title",)

    @permalink
    def get_absolute_url(self):
        return ("blog_post_list_category", (), {"category": self.slug})


class BlogPost(Displayable, Ownable, RichText):
    """
    A blog post.
    """
    categories = models.ManyToManyField(BlogCategory,
                                        verbose_name=_("Categories"),
                                        blank=True, related_name="blogposts")
    allow_comments = models.BooleanField(verbose_name=_("Allow comments"),
                                         default=True)
    # comments = CommentsField(verbose_name=_("Comments"))
    related_posts = models.ManyToManyField("self",
                                           verbose_name=_("Related posts"), blank=True)

    class Meta:
        verbose_name = _("Blog Post")
        verbose_name_plural = _("Blog Posts")
        ordering = ("-publish_date",)

    @permalink
    def get_absolute_url(self):
        """
        """
        url_name = "blog_post_detail"
        kwargs = {"slug": self.slug}
        return (url_name, None, kwargs)


class FeaturedImage(TimeStamped):
    image = CloudinaryField('image')
    model = models.ForeignKey(BlogPost, null=True, blank=True)
    description = models.CharField(max_length=100, blank=True, null=True)
    is_visible = models.BooleanField(default=True)
    is_featured_image = models.BooleanField(default=False)
    src = models.URLField()
    filename = models.CharField(max_length=300)

    def save(self, *args, **kwargs):
        if not self.src:
            self.src = self.image.url
        if not self.filename:
            self.filename = self.image.name
        super(FeaturedImage, self).save(*args, **kwargs)


class Message(models.Model):
    name = models.CharField(max_length=100, blank=True, null=True)
    subject = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return u'%s - %s' % (self.name, self.email)
