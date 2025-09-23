from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import Response
from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorDatabase

from models.user import User
from models.blog import (
    BlogPost, BlogPostCreate, BlogPostUpdate, BlogPostResponse,
    Comment, CommentCreate, BulkOperation, BulkOperationCreate,
    SEOSettings, SEOPage, PostStatus, PostCategory
)
from services.blog_service import BlogService
from utils.auth import get_current_user, get_optional_current_user

# Database dependency
async def get_database() -> AsyncIOMotorDatabase:
    from motor.motor_asyncio import AsyncIOMotorClient
    import os
    mongo_url = os.environ['MONGO_URL']
    client = AsyncIOMotorClient(mongo_url)
    return client[os.environ.get('DB_NAME', 'xfas_logistics')]

router = APIRouter(prefix="/blog", tags=["Blog"])

# ===== BLOG POSTS =====

@router.post("/posts", response_model=BlogPost)
async def create_blog_post(
    post_data: BlogPostCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Create a new blog post (admin only)."""
    
    try:
        blog_service = BlogService()
        post = await blog_service.create_blog_post(
            post_data, 
            current_user.id, 
            f"{current_user.first_name} {current_user.last_name}",
            db
        )
        
        return post
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating blog post: {str(e)}"
        )

@router.get("/posts")
async def get_blog_posts(
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
    category: Optional[PostCategory] = Query(None),
    status: Optional[PostStatus] = Query(None),
    search: Optional[str] = Query(None),
    featured_only: bool = Query(False),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get blog posts with filtering and pagination (public endpoint)."""
    
    try:
        blog_service = BlogService()
        posts, total_count = await blog_service.get_blog_posts(
            db=db,
            limit=limit,
            skip=skip,
            category=category,
            status=status or PostStatus.PUBLISHED,  # Default to published for public
            search=search,
            featured_only=featured_only
        )
        
        return {
            "success": True,
            "data": {
                "posts": posts,
                "total_count": total_count,
                "page_info": {
                    "limit": limit,
                    "skip": skip,
                    "has_more": total_count > (skip + limit)
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting blog posts: {str(e)}"
        )

@router.get("/posts/{slug}", response_model=BlogPostResponse)
async def get_blog_post_by_slug(
    slug: str,
    increment_views: bool = Query(True),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get a blog post by slug (public endpoint)."""
    
    try:
        blog_service = BlogService()
        post = await blog_service.get_blog_post_by_slug(slug, db, increment_views)
        
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blog post not found"
            )
        
        return post
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting blog post: {str(e)}"
        )

@router.put("/posts/{post_id}", response_model=BlogPost)
async def update_blog_post(
    post_id: str,
    update_data: BlogPostUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update a blog post (admin only)."""
    
    try:
        blog_service = BlogService()
        post = await blog_service.update_blog_post(post_id, update_data, db)
        
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blog post not found"
            )
        
        return post
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating blog post: {str(e)}"
        )

@router.delete("/posts/{post_id}")
async def delete_blog_post(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Delete a blog post (admin only)."""
    
    try:
        blog_service = BlogService()
        deleted = await blog_service.delete_blog_post(post_id, db)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blog post not found"
            )
        
        return {"success": True, "message": "Blog post deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting blog post: {str(e)}"
        )

# ===== COMMENTS =====

@router.post("/posts/{post_id}/comments", response_model=Comment)
async def create_comment(
    post_id: str,
    comment_data: CommentCreate,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Create a comment on a blog post (public endpoint)."""
    
    try:
        # Ensure post_id matches
        comment_data.post_id = post_id
        
        blog_service = BlogService()
        comment = await blog_service.create_comment(comment_data, db)
        
        return comment
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating comment: {str(e)}"
        )

@router.get("/posts/{post_id}/comments", response_model=List[Comment])
async def get_comments(
    post_id: str,
    status_filter: str = Query("approved"),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get comments for a blog post (public endpoint)."""
    
    try:
        blog_service = BlogService()
        comments = await blog_service.get_comments(post_id, db, status_filter)
        
        return comments
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting comments: {str(e)}"
        )

# ===== BULK OPERATIONS =====

@router.post("/bulk-operations", response_model=BulkOperation)
async def create_bulk_operation(
    operation_data: BulkOperationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Create a new bulk operation."""
    
    try:
        blog_service = BlogService()
        operation = await blog_service.create_bulk_operation(operation_data, current_user.id, db)
        
        return operation
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating bulk operation: {str(e)}"
        )

@router.get("/bulk-operations", response_model=List[BulkOperation])
async def get_bulk_operations(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user's bulk operations."""
    
    try:
        blog_service = BlogService()
        operations = await blog_service.get_bulk_operations(current_user.id, db, limit)
        
        return operations
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting bulk operations: {str(e)}"
        )

@router.post("/bulk-operations/{operation_id}/import")
async def import_csv_data(
    operation_id: str,
    entity_type: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Import CSV data for bulk operation."""
    
    try:
        # Validate file type
        if not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only CSV files are supported"
            )
        
        # Read file content
        content = await file.read()
        csv_content = content.decode('utf-8')
        
        blog_service = BlogService()
        result = await blog_service.process_csv_import(operation_id, csv_content, entity_type, db)
        
        return {"success": True, "data": result}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error importing CSV data: {str(e)}"
        )

@router.get("/bulk-operations/{operation_id}/export")
async def export_csv_data(
    operation_id: str,
    entity_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Export data to CSV format."""
    
    try:
        blog_service = BlogService()
        csv_content = await blog_service.export_to_csv(entity_type, {}, db)
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={entity_type}_export.csv"}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error exporting CSV data: {str(e)}"
        )

# ===== SEO MANAGEMENT =====

@router.get("/seo/settings", response_model=SEOSettings)
async def get_seo_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get SEO settings (admin only)."""
    
    try:
        blog_service = BlogService()
        settings = await blog_service.get_seo_settings(db)
        
        return settings
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting SEO settings: {str(e)}"
        )

@router.put("/seo/settings", response_model=SEOSettings)
async def update_seo_settings(
    update_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update SEO settings (admin only)."""
    
    try:
        blog_service = BlogService()
        settings = await blog_service.update_seo_settings(update_data, db)
        
        return settings
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating SEO settings: {str(e)}"
        )

@router.get("/seo/pages/{page_path:path}")
async def get_page_seo(
    page_path: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get SEO settings for a specific page (public endpoint)."""
    
    try:
        blog_service = BlogService()
        page_seo = await blog_service.get_page_seo(f"/{page_path}", db)
        
        if not page_seo:
            # Return default SEO for the page
            return {
                "title": "XFas Logistics - Multi-Channel Shipping Solutions",
                "description": "Leading logistics platform offering domestic and international shipping with AI-powered recommendations and real-time tracking.",
                "keywords": ["logistics", "shipping", "courier", "delivery", "tracking"]
            }
        
        return page_seo
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting page SEO: {str(e)}"
        )

@router.get("/sitemap.xml")
async def get_sitemap(
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Generate and return XML sitemap (public endpoint)."""
    
    try:
        blog_service = BlogService()
        base_url = "https://xfaslogistics.com"  # Should be configurable
        sitemap_xml = await blog_service.generate_sitemap(base_url, db)
        
        return Response(
            content=sitemap_xml,
            media_type="application/xml",
            headers={"Content-Type": "application/xml"}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating sitemap: {str(e)}"
        )