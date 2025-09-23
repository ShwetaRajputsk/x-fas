from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class PostStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    SCHEDULED = "scheduled"

class PostCategory(str, Enum):
    LOGISTICS = "logistics"
    SHIPPING = "shipping"
    BUSINESS = "business"
    TECHNOLOGY = "technology"
    INDUSTRY_NEWS = "industry_news"
    TIPS_GUIDES = "tips_guides"
    COMPANY_NEWS = "company_news"

class BlogPost(BaseModel):
    id: str = Field(default_factory=lambda: __import__('uuid').uuid4().hex)
    title: str
    slug: str
    excerpt: Optional[str] = None
    content: str
    featured_image: Optional[str] = None
    
    # SEO fields
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    meta_keywords: List[str] = []
    
    # Organization
    category: PostCategory
    tags: List[str] = []
    
    # Publishing
    status: PostStatus = PostStatus.DRAFT
    published_at: Optional[datetime] = None
    scheduled_for: Optional[datetime] = None
    
    # Author info
    author_id: str
    author_name: str
    author_bio: Optional[str] = None
    author_avatar: Optional[str] = None
    
    # Engagement
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    
    # Content settings
    allow_comments: bool = True
    featured: bool = False
    sticky: bool = False
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class BlogPostCreate(BaseModel):
    title: str
    slug: Optional[str] = None
    excerpt: Optional[str] = None
    content: str
    featured_image: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    meta_keywords: List[str] = []
    category: PostCategory
    tags: List[str] = []
    status: PostStatus = PostStatus.DRAFT
    scheduled_for: Optional[datetime] = None
    allow_comments: bool = True
    featured: bool = False
    sticky: bool = False

class BlogPostUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    excerpt: Optional[str] = None
    content: Optional[str] = None
    featured_image: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    meta_keywords: Optional[List[str]] = None
    category: Optional[PostCategory] = None
    tags: Optional[List[str]] = None
    status: Optional[PostStatus] = None
    scheduled_for: Optional[datetime] = None
    allow_comments: Optional[bool] = None
    featured: Optional[bool] = None
    sticky: Optional[bool] = None

class BlogPostResponse(BaseModel):
    id: str
    title: str
    slug: str
    excerpt: Optional[str]
    content: str
    featured_image: Optional[str]
    meta_title: Optional[str]
    meta_description: Optional[str]
    meta_keywords: List[str]
    category: PostCategory
    tags: List[str]
    status: PostStatus
    published_at: Optional[datetime]
    author_name: str
    author_bio: Optional[str]
    author_avatar: Optional[str]
    view_count: int
    like_count: int
    comment_count: int
    featured: bool
    sticky: bool
    created_at: datetime
    updated_at: datetime

class Comment(BaseModel):
    id: str = Field(default_factory=lambda: __import__('uuid').uuid4().hex)
    post_id: str
    author_name: str
    author_email: str
    author_website: Optional[str] = None
    content: str
    status: str = "pending"  # 'pending', 'approved', 'spam', 'trash'
    parent_id: Optional[str] = None  # For nested comments
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CommentCreate(BaseModel):
    post_id: str
    author_name: str
    author_email: str
    author_website: Optional[str] = None
    content: str
    parent_id: Optional[str] = None

class BulkOperation(BaseModel):
    id: str = Field(default_factory=lambda: __import__('uuid').uuid4().hex)
    operation_type: str  # 'import', 'export', 'update', 'delete'
    entity_type: str  # 'shipments', 'users', 'quotes', 'rates'
    status: str = "pending"  # 'pending', 'processing', 'completed', 'failed'
    
    # File information
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    
    # Processing details
    total_records: int = 0
    processed_records: int = 0
    success_count: int = 0
    error_count: int = 0
    
    # Progress tracking
    progress_percentage: float = 0.0
    current_step: Optional[str] = None
    
    # Results
    result_file_path: Optional[str] = None
    error_log: List[Dict[str, Any]] = []
    summary: Optional[Dict[str, Any]] = None
    
    # User and timing
    user_id: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class BulkOperationCreate(BaseModel):
    operation_type: str
    entity_type: str
    file_name: Optional[str] = None
    total_records: int = 0

class SEOSettings(BaseModel):
    id: str = Field(default_factory=lambda: __import__('uuid').uuid4().hex)
    
    # General SEO
    site_title: str = "XFas Logistics - Multi-Channel Shipping Solutions"
    site_description: str = "Leading logistics platform offering domestic and international shipping with AI-powered recommendations and real-time tracking."
    site_keywords: List[str] = ["logistics", "shipping", "courier", "delivery", "tracking", "international shipping"]
    
    # Social media
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None
    twitter_card: str = "summary_large_image"
    twitter_site: Optional[str] = None
    
    # Technical SEO
    robots_txt: str = "User-agent: *\nAllow: /\nSitemap: /sitemap.xml"
    canonical_url: str = "https://xfaslogistics.com"
    
    # Schema.org structured data
    organization_schema: Dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "XFas Logistics Private Limited",
        "url": "https://xfaslogistics.com",
        "logo": "https://xfaslogistics.com/logo.png",
        "description": "Multi-channel parcel delivery service",
        "address": {
            "@type": "PostalAddress",
            "addressCountry": "IN"
        }
    }
    
    # Analytics
    google_analytics_id: Optional[str] = None
    google_tag_manager_id: Optional[str] = None
    facebook_pixel_id: Optional[str] = None
    
    # Performance
    enable_compression: bool = True
    enable_caching: bool = True
    minify_css: bool = True
    minify_js: bool = True
    
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class SEOPage(BaseModel):
    id: str = Field(default_factory=lambda: __import__('uuid').uuid4().hex)
    page_path: str  # e.g., "/", "/quote", "/track"
    title: str
    description: str
    keywords: List[str] = []
    canonical_url: Optional[str] = None
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None
    no_index: bool = False
    no_follow: bool = False
    schema_markup: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)