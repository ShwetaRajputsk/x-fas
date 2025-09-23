from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import re
import csv
import io
import json
from motor.motor_asyncio import AsyncIOMotorDatabase

from models.blog import (
    BlogPost, BlogPostCreate, BlogPostUpdate, BlogPostResponse,
    Comment, CommentCreate, BulkOperation, BulkOperationCreate,
    SEOSettings, SEOPage, PostStatus, PostCategory
)

class BlogService:
    def __init__(self):
        pass
    
    # ===== BLOG POST MANAGEMENT =====
    
    def _generate_slug(self, title: str) -> str:
        """Generate URL-friendly slug from title."""
        slug = re.sub(r'[^\w\s-]', '', title.lower())
        slug = re.sub(r'[\s_-]+', '-', slug)
        return slug.strip('-')
    
    async def create_blog_post(self, post_data: BlogPostCreate, author_id: str, author_name: str, db: AsyncIOMotorDatabase) -> BlogPost:
        """Create a new blog post."""
        
        # Generate slug if not provided
        slug = post_data.slug or self._generate_slug(post_data.title)
        
        # Ensure slug is unique
        existing_post = await db.blog_posts.find_one({"slug": slug})
        if existing_post:
            counter = 1
            original_slug = slug
            while existing_post:
                slug = f"{original_slug}-{counter}"
                existing_post = await db.blog_posts.find_one({"slug": slug})
                counter += 1
        
        # Set published_at if status is published
        published_at = None
        if post_data.status == PostStatus.PUBLISHED:
            published_at = datetime.utcnow()
        elif post_data.status == PostStatus.SCHEDULED and post_data.scheduled_for:
            published_at = post_data.scheduled_for
        
        blog_post = BlogPost(
            **post_data.dict(exclude={'slug'}),
            slug=slug,
            author_id=author_id,
            author_name=author_name,
            published_at=published_at
        )
        
        await db.blog_posts.insert_one(blog_post.dict())
        return blog_post
    
    async def get_blog_posts(self, 
                           db: AsyncIOMotorDatabase,
                           limit: int = 20, 
                           skip: int = 0, 
                           category: Optional[PostCategory] = None,
                           status: Optional[PostStatus] = None,
                           search: Optional[str] = None,
                           featured_only: bool = False) -> Tuple[List[BlogPostResponse], int]:
        """Get blog posts with filtering and pagination."""
        
        query = {}
        
        # Status filter (default to published for public access)
        if status:
            query["status"] = status
        else:
            query["status"] = PostStatus.PUBLISHED
        
        # Category filter
        if category:
            query["category"] = category
        
        # Featured filter
        if featured_only:
            query["featured"] = True
        
        # Search filter
        if search:
            query["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"excerpt": {"$regex": search, "$options": "i"}},
                {"content": {"$regex": search, "$options": "i"}},
                {"tags": {"$regex": search, "$options": "i"}}
            ]
        
        # Get posts
        cursor = db.blog_posts.find(query).sort([
            ("sticky", -1),  # Sticky posts first
            ("published_at", -1)  # Then by publish date
        ]).skip(skip).limit(limit)
        
        posts_data = await cursor.to_list(length=limit)
        total_count = await db.blog_posts.count_documents(query)
        
        # Convert to response format
        posts = [BlogPostResponse(**post) for post in posts_data]
        
        return posts, total_count
    
    async def get_blog_post_by_slug(self, slug: str, db: AsyncIOMotorDatabase, increment_views: bool = False) -> Optional[BlogPostResponse]:
        """Get a blog post by slug."""
        
        post_data = await db.blog_posts.find_one({"slug": slug})
        if not post_data:
            return None
        
        # Increment view count if requested
        if increment_views:
            await db.blog_posts.update_one(
                {"slug": slug},
                {"$inc": {"view_count": 1}}
            )
            post_data["view_count"] += 1
        
        return BlogPostResponse(**post_data)
    
    async def update_blog_post(self, post_id: str, update_data: BlogPostUpdate, db: AsyncIOMotorDatabase) -> Optional[BlogPost]:
        """Update a blog post."""
        
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        update_dict["updated_at"] = datetime.utcnow()
        
        # Handle slug update
        if "title" in update_dict and "slug" not in update_dict:
            update_dict["slug"] = self._generate_slug(update_dict["title"])
        elif "slug" in update_dict:
            update_dict["slug"] = self._generate_slug(update_dict["slug"])
        
        # Handle status change to published
        if update_dict.get("status") == PostStatus.PUBLISHED:
            existing_post = await db.blog_posts.find_one({"id": post_id})
            if existing_post and existing_post.get("status") != PostStatus.PUBLISHED:
                update_dict["published_at"] = datetime.utcnow()
        
        result = await db.blog_posts.update_one(
            {"id": post_id},
            {"$set": update_dict}
        )
        
        if result.modified_count:
            updated_data = await db.blog_posts.find_one({"id": post_id})
            return BlogPost(**updated_data)
        
        return None
    
    async def delete_blog_post(self, post_id: str, db: AsyncIOMotorDatabase) -> bool:
        """Delete a blog post."""
        
        result = await db.blog_posts.delete_one({"id": post_id})
        return result.deleted_count > 0
    
    # ===== COMMENT MANAGEMENT =====
    
    async def create_comment(self, comment_data: CommentCreate, db: AsyncIOMotorDatabase) -> Comment:
        """Create a new comment."""
        
        comment = Comment(**comment_data.dict())
        await db.comments.insert_one(comment.dict())
        
        # Increment comment count on post
        await db.blog_posts.update_one(
            {"id": comment_data.post_id},
            {"$inc": {"comment_count": 1}}
        )
        
        return comment
    
    async def get_comments(self, post_id: str, db: AsyncIOMotorDatabase, status: str = "approved") -> List[Comment]:
        """Get comments for a post."""
        
        cursor = db.comments.find({
            "post_id": post_id,
            "status": status
        }).sort("created_at", 1)
        
        comments_data = await cursor.to_list(length=1000)
        return [Comment(**comment) for comment in comments_data]
    
    # ===== BULK OPERATIONS =====
    
    async def create_bulk_operation(self, operation_data: BulkOperationCreate, user_id: str, db: AsyncIOMotorDatabase) -> BulkOperation:
        """Create a new bulk operation."""
        
        operation = BulkOperation(
            **operation_data.dict(),
            user_id=user_id
        )
        
        await db.bulk_operations.insert_one(operation.dict())
        return operation
    
    async def get_bulk_operations(self, user_id: str, db: AsyncIOMotorDatabase, limit: int = 50) -> List[BulkOperation]:
        """Get user's bulk operations."""
        
        cursor = db.bulk_operations.find({"user_id": user_id}).sort("created_at", -1).limit(limit)
        operations_data = await cursor.to_list(length=limit)
        
        return [BulkOperation(**op) for op in operations_data]
    
    async def update_bulk_operation(self, operation_id: str, update_data: Dict[str, Any], db: AsyncIOMotorDatabase) -> bool:
        """Update bulk operation status and progress."""
        
        result = await db.bulk_operations.update_one(
            {"id": operation_id},
            {"$set": update_data}
        )
        
        return result.modified_count > 0
    
    async def process_csv_import(self, operation_id: str, csv_content: str, entity_type: str, db: AsyncIOMotorDatabase) -> Dict[str, Any]:
        """Process CSV import for bulk operations."""
        
        results = {
            "total_records": 0,
            "success_count": 0,
            "error_count": 0,
            "errors": []
        }
        
        try:
            # Update operation status
            await self.update_bulk_operation(operation_id, {
                "status": "processing",
                "started_at": datetime.utcnow(),
                "current_step": "Reading CSV file"
            }, db)
            
            # Parse CSV
            csv_reader = csv.DictReader(io.StringIO(csv_content))
            rows = list(csv_reader)
            results["total_records"] = len(rows)
            
            # Update progress
            await self.update_bulk_operation(operation_id, {
                "total_records": len(rows),
                "current_step": f"Processing {entity_type} records"
            }, db)
            
            # Process each row based on entity type
            for i, row in enumerate(rows):
                try:
                    if entity_type == "shipments":
                        await self._process_shipment_row(row, db)
                    elif entity_type == "users":
                        await self._process_user_row(row, db)
                    elif entity_type == "rates":
                        await self._process_rate_row(row, db)
                    
                    results["success_count"] += 1
                    
                except Exception as row_error:
                    results["error_count"] += 1
                    results["errors"].append({
                        "row": i + 1,
                        "error": str(row_error),
                        "data": row
                    })
                
                # Update progress
                progress = ((i + 1) / len(rows)) * 100
                await self.update_bulk_operation(operation_id, {
                    "processed_records": i + 1,
                    "progress_percentage": progress,
                    "success_count": results["success_count"],
                    "error_count": results["error_count"]
                }, db)
            
            # Mark as completed
            await self.update_bulk_operation(operation_id, {
                "status": "completed",
                "completed_at": datetime.utcnow(),
                "current_step": "Completed",
                "summary": results
            }, db)
            
        except Exception as e:
            # Mark as failed
            await self.update_bulk_operation(operation_id, {
                "status": "failed",
                "completed_at": datetime.utcnow(),
                "current_step": f"Failed: {str(e)}",
                "summary": results
            }, db)
            
            results["errors"].append({
                "row": "general",
                "error": str(e),
                "data": {}
            })
        
        return results
    
    async def _process_shipment_row(self, row: Dict[str, Any], db: AsyncIOMotorDatabase):
        """Process a single shipment row from CSV."""
        # Implementation would depend on CSV format
        # This is a placeholder for actual shipment creation logic
        pass
    
    async def _process_user_row(self, row: Dict[str, Any], db: AsyncIOMotorDatabase):
        """Process a single user row from CSV."""
        # Implementation would depend on CSV format
        # This is a placeholder for actual user creation logic
        pass
    
    async def _process_rate_row(self, row: Dict[str, Any], db: AsyncIOMotorDatabase):
        """Process a single rate row from CSV."""
        # Implementation would depend on CSV format
        # This is a placeholder for actual rate creation logic
        pass
    
    async def export_to_csv(self, entity_type: str, filters: Dict[str, Any], db: AsyncIOMotorDatabase) -> str:
        """Export data to CSV format."""
        
        output = io.StringIO()
        
        if entity_type == "shipments":
            # Export shipments
            cursor = db.shipments.find(filters)
            shipments = await cursor.to_list(length=10000)
            
            if shipments:
                fieldnames = ["id", "shipment_number", "status", "sender_name", "recipient_name", 
                             "carrier", "cost", "created_at"]
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                
                for shipment in shipments:
                    writer.writerow({
                        "id": shipment.get("id"),
                        "shipment_number": shipment.get("shipment_number"),
                        "status": shipment.get("status"),
                        "sender_name": shipment.get("sender", {}).get("name"),
                        "recipient_name": shipment.get("recipient", {}).get("name"),
                        "carrier": shipment.get("carrier_info", {}).get("carrier_name"),
                        "cost": shipment.get("payment_info", {}).get("amount"),
                        "created_at": shipment.get("created_at")
                    })
        
        elif entity_type == "users":
            # Export users
            cursor = db.users.find(filters)
            users = await cursor.to_list(length=10000)
            
            if users:
                fieldnames = ["id", "first_name", "last_name", "email", "user_type", 
                             "is_active", "created_at"]
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                
                for user in users:
                    writer.writerow({
                        "id": user.get("id"),
                        "first_name": user.get("first_name"),
                        "last_name": user.get("last_name"),
                        "email": user.get("email"),
                        "user_type": user.get("user_type"),
                        "is_active": user.get("is_active"),
                        "created_at": user.get("created_at")
                    })
        
        return output.getvalue()
    
    # ===== SEO MANAGEMENT =====
    
    async def get_seo_settings(self, db: AsyncIOMotorDatabase) -> SEOSettings:
        """Get SEO settings."""
        
        settings_data = await db.seo_settings.find_one({})
        if settings_data:
            return SEOSettings(**settings_data)
        else:
            # Create default settings
            default_settings = SEOSettings()
            await db.seo_settings.insert_one(default_settings.dict())
            return default_settings
    
    async def update_seo_settings(self, update_data: Dict[str, Any], db: AsyncIOMotorDatabase) -> SEOSettings:
        """Update SEO settings."""
        
        update_data["updated_at"] = datetime.utcnow()
        
        await db.seo_settings.update_one(
            {},
            {"$set": update_data},
            upsert=True
        )
        
        return await self.get_seo_settings(db)
    
    async def get_page_seo(self, page_path: str, db: AsyncIOMotorDatabase) -> Optional[SEOPage]:
        """Get SEO settings for a specific page."""
        
        page_data = await db.seo_pages.find_one({"page_path": page_path})
        if page_data:
            return SEOPage(**page_data)
        return None
    
    async def update_page_seo(self, page_path: str, seo_data: Dict[str, Any], db: AsyncIOMotorDatabase) -> SEOPage:
        """Update SEO settings for a specific page."""
        
        seo_data["page_path"] = page_path
        seo_data["updated_at"] = datetime.utcnow()
        
        await db.seo_pages.update_one(
            {"page_path": page_path},
            {"$set": seo_data},
            upsert=True
        )
        
        updated_data = await db.seo_pages.find_one({"page_path": page_path})
        return SEOPage(**updated_data)
    
    async def generate_sitemap(self, base_url: str, db: AsyncIOMotorDatabase) -> str:
        """Generate XML sitemap."""
        
        sitemap_entries = []
        
        # Static pages
        static_pages = [
            {"url": f"{base_url}/", "priority": "1.0", "changefreq": "daily"},
            {"url": f"{base_url}/quote", "priority": "0.9", "changefreq": "weekly"},
            {"url": f"{base_url}/track", "priority": "0.9", "changefreq": "weekly"},
            {"url": f"{base_url}/blog", "priority": "0.8", "changefreq": "daily"},
        ]
        
        sitemap_entries.extend(static_pages)
        
        # Blog posts
        cursor = db.blog_posts.find({"status": PostStatus.PUBLISHED})
        posts = await cursor.to_list(length=10000)
        
        for post in posts:
            sitemap_entries.append({
                "url": f"{base_url}/blog/{post['slug']}",
                "priority": "0.7",
                "changefreq": "weekly",
                "lastmod": post.get("updated_at", post.get("created_at"))
            })
        
        # Generate XML
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        
        for entry in sitemap_entries:
            xml += '  <url>\n'
            xml += f'    <loc>{entry["url"]}</loc>\n'
            xml += f'    <priority>{entry["priority"]}</priority>\n'
            xml += f'    <changefreq>{entry["changefreq"]}</changefreq>\n'
            if entry.get("lastmod"):
                lastmod = entry["lastmod"]
                if isinstance(lastmod, str):
                    lastmod = datetime.fromisoformat(lastmod)
                xml += f'    <lastmod>{lastmod.strftime("%Y-%m-%d")}</lastmod>\n'
            xml += '  </url>\n'
        
        xml += '</urlset>'
        
        return xml