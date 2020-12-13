from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView
from django.http import HttpResponse
from .models import Post, Comment
from .forms import EmailPostForm, CommentForm
from django.core.mail import send_mail
from taggit.models import Tag
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from .forms import EmailPostForm, CommentForm, SearchForm

# class PostListView(ListView):
#     queryset = Post.published.all()
#     context_object_name = 'posts'
#     paginate_by = 3
#     template_name = 'blog/post/list.html'


def post_list(request, tag_slug=None):
    object_list = Post.published.all()
    tag = None
    paginator = Paginator(object_list, 3)  # По 3 статьи на каждой странице.
    page = request.GET.get('page')
    if tag_slug:
        tag = get_object_or_404(Tag, slug=tag_slug)
        object_list = object_list.filter(tag__in=[tag])
        paginator = Paginator(object_list, 2)
    try:
        posts = paginator.page(page)
    except PageNotAnInteger:
        posts = paginator.page(1)  # Если указанная страница не является целым числом.
    except EmptyPage:
        posts = paginator.page(paginator.num_pages)  # Если указанный номер больше, чем всего страниц, возвращаем последнюю.
    return render(request, 'blog/post/list.html', {'page': page, 'posts': posts, 'tag': tag})


def post_share(request, post_id):
    post = get_object_or_404(Post, id=post_id, status='published')
    sent = False
    if request.method == 'POST':
        form = EmailPostForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            post_url = request.build_absolute_uri(post.get_absolute_url())
            subject = '{} ({}) recommends you reading "{}"'.format(cd['name'], cd['email'], post.title)
            message = 'Read "{}" at {}\n\n{}\'s comments:' '{}'.format(post.title, post_url, cd['name'], cd['comments'])
            send_mail(subject, message, 'admin@myblog.com', [cd['to']])
            sent = True
        else:
            form = EmailPostForm()
        return render(request, 'blog/post/share.html', {'post': post, 'form': form, 'sent': sent})


def post_detail(request, year, month, day, post):
    post = get_object_or_404(Post, slug=post, status='published', publish__year=year, publish__month=month, publish__day=day)
    comments = post.comments.filter(active=True)
    new_comment = None
    post_tags_ids = post.tag.values_list('id', flat=True)
    similar_posts = Post.published.filter(tag__in=post_tags_ids).exclude(id=post.id)
    similar_posts = similar_posts.annotate(same_tag=Count('tag')).order_by('-same_tag', '-publish')[:4]
    if request.method == 'POST':
        # Пользователь отправил комментарий.
        comment_form = CommentForm(data=request.POST)
        if comment_form.is_valid():
            # Создаем комментарий, но пока не сохраняем в базе данных.
            new_comment = comment_form.save(commit=False)
            # Привязываем комментарий к текущей статье.
            new_comment.post = post
            # Сохраняем комментарий в базе данных.
            new_comment.save()
        else:
            comment_form = CommentForm()
        return render(request, 'blog/post/detail.html', {'post': post, 'comments': comments, 'new_comment': new_comment, 'comment_form': comment_form})

    return render(request, 'blog/post/detail.html', {'post': post, 'comments': comments, 'new_comment': new_comment, 'similar_posts': similar_posts})


def post_search(request):
    form = SearchForm()
    query = None
    results = []
    if 'query' in request.GET:
        form = SearchForm(request.GET)
    if form.is_valid():
        query = form.cleaned_data['query']
        search_vector = SearchVector('title', 'body')
        search_query = SearchQuery(query)
        results = Post.objects.annotate(
            search=search_vector,
            rank=SearchRank(search_vector, search_query)).filter(search=search_query).order_by('-rank')
    return render(request, 'blog/post/search.html', {'form': form, 'query': query, 'results': results})

