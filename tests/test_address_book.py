import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from models.address_book import (
    SavedAddressCreate, SavedAddressUpdate, AddressType, AddressCategory
)
from services.address_book_service import AddressBookService

# Mock database for testing
@pytest.fixture
async def mock_db():
    """Create a mock database for testing"""
    mock_collection = AsyncMock()
    mock_db = MagicMock()
    mock_db.saved_addresses = mock_collection
    
    service = AddressBookService()
    service.db = mock_db
    service.collection = mock_collection
    
    return service, mock_collection

@pytest.fixture
def sample_address_data():
    """Sample address data for testing"""
    return SavedAddressCreate(
        label="Home Address",
        address_type=AddressType.BOTH,
        category=AddressCategory.HOME,
        name="John Doe",
        company="Tech Corp",
        phone="9876543210",
        email="john@example.com",
        street="123 Tech Street, Block A",
        city="Mumbai",
        state="Maharashtra",
        postal_code="400001",
        country="India",
        landmark="Near Metro Station",
        is_default_pickup=True,
        is_default_delivery=False
    )

@pytest.fixture
def sample_saved_address():
    """Sample saved address response"""
    return {
        "id": "address-123",
        "user_id": "user-123",
        "label": "Home Address",
        "address_type": "both",
        "category": "home",
        "name": "John Doe",
        "company": "Tech Corp",
        "phone": "+919876543210",
        "email": "john@example.com",
        "street": "123 Tech Street, Block A",
        "city": "Mumbai",
        "state": "Maharashtra",
        "postal_code": "400001",
        "country": "India",
        "landmark": "Near Metro Station",
        "is_default_pickup": True,
        "is_default_delivery": False,
        "is_active": True,
        "usage_count": 0,
        "last_used_at": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

class TestAddressBookService:
    """Test cases for AddressBookService"""
    
    @pytest.mark.asyncio
    async def test_create_address_success(self, mock_db, sample_address_data):
        """Test successful address creation"""
        service, mock_collection = mock_db
        
        # Mock database responses
        mock_collection.insert_one.return_value.inserted_id = "mock_id"
        mock_collection.find_one.return_value = {
            "id": "address-123",
            "user_id": "user-123",
            **sample_address_data.dict()
        }
        
        # Test address creation
        result = await service.create_address("user-123", sample_address_data)
        
        # Verify the result
        assert result is not None
        assert result.label == "Home Address"
        assert result.phone == "+919876543210"  # Phone should be formatted
        
        # Verify database calls
        mock_collection.insert_one.assert_called_once()
        mock_collection.find_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_phone_validation(self):
        """Test phone number validation"""
        # Test valid Indian phone numbers
        test_cases = [
            ("9876543210", "+919876543210"),
            ("919876543210", "+919876543210"),
            ("+919876543210", "+919876543210"),
            ("8123456789", "+918123456789"),
        ]
        
        for input_phone, expected in test_cases:
            address_data = SavedAddressCreate(
                label="Test Address",
                name="Test User",
                phone=input_phone,
                email="test@example.com",
                street="Test Street 123",
                city="Mumbai",
                state="Maharashtra",
                postal_code="400001"
            )
            assert address_data.phone == expected
    
    @pytest.mark.asyncio
    async def test_phone_validation_invalid(self):
        """Test invalid phone number validation"""
        with pytest.raises(ValueError, match="Invalid Indian phone number"):
            SavedAddressCreate(
                label="Test Address",
                name="Test User",
                phone="12345",  # Invalid phone
                email="test@example.com",
                street="Test Street 123",
                city="Mumbai",
                state="Maharashtra",
                postal_code="400001"
            )
    
    @pytest.mark.asyncio
    async def test_postal_code_validation(self):
        """Test postal code validation for India"""
        # Valid postal code
        address_data = SavedAddressCreate(
            label="Test Address",
            name="Test User",
            phone="9876543210",
            email="test@example.com",
            street="Test Street 123",
            city="Mumbai",
            state="Maharashtra",
            postal_code="400001",
            country="India"
        )
        assert address_data.postal_code == "400001"
        
        # Invalid postal code
        with pytest.raises(ValueError, match="Indian postal code must be 6 digits"):
            SavedAddressCreate(
                label="Test Address",
                name="Test User",
                phone="9876543210",
                email="test@example.com",
                street="Test Street 123",
                city="Mumbai",
                state="Maharashtra",
                postal_code="12345",  # Invalid - only 5 digits
                country="India"
            )
    
    @pytest.mark.asyncio
    async def test_get_user_addresses(self, mock_db):
        """Test getting user addresses with filtering"""
        service, mock_collection = mock_db
        
        # Mock addresses
        mock_addresses = [
            {"id": "addr1", "address_type": "pickup", "category": "home"},
            {"id": "addr2", "address_type": "delivery", "category": "office"},
            {"id": "addr3", "address_type": "both", "category": "warehouse"}
        ]
        
        mock_collection.find.return_value.skip.return_value.limit.return_value.sort.return_value.to_list.return_value = mock_addresses
        
        # Test with filters
        addresses = await service.get_user_addresses(
            user_id="user-123",
            address_type=AddressType.PICKUP,
            category=AddressCategory.HOME,
            limit=10,
            offset=0
        )
        
        # Verify query was called
        mock_collection.find.assert_called_once()
        
        # Check filter construction
        query_args = mock_collection.find.call_args[0][0]
        assert query_args["user_id"] == "user-123"
        assert query_args["is_active"] == True
        assert "$in" in query_args["address_type"]
        assert "pickup" in query_args["address_type"]["$in"]
        assert "both" in query_args["address_type"]["$in"]
    
    @pytest.mark.asyncio
    async def test_set_default_address(self, mock_db):
        """Test setting an address as default"""
        service, mock_collection = mock_db
        
        # Mock successful update
        mock_collection.update_many.return_value = AsyncMock()
        mock_collection.update_one.return_value.modified_count = 1
        
        # Test setting default pickup address
        result = await service.set_default_address(
            "user-123", "address-123", AddressType.PICKUP
        )
        
        assert result == True
        
        # Verify unset previous defaults was called
        mock_collection.update_many.assert_called_once()
        
        # Verify set new default was called
        mock_collection.update_one.assert_called_once()
        update_args = mock_collection.update_one.call_args[0]
        assert update_args[0]["id"] == "address-123"
        assert update_args[0]["user_id"] == "user-123"
        assert update_args[1]["$set"]["is_default_pickup"] == True
    
    @pytest.mark.asyncio
    async def test_search_addresses(self, mock_db):
        """Test address search functionality"""
        service, mock_collection = mock_db
        
        # Mock search results
        mock_results = [
            {"id": "addr1", "label": "Home Office", "city": "Mumbai"},
            {"id": "addr2", "label": "Work Place", "city": "Delhi"}
        ]
        
        mock_collection.find.return_value.sort.return_value.limit.return_value.to_list.return_value = mock_results
        
        # Test search
        results = await service.search_addresses(
            user_id="user-123",
            query="office",
            address_type=AddressType.BOTH,
            limit=20
        )
        
        # Verify search query
        mock_collection.find.assert_called_once()
        query_args = mock_collection.find.call_args[0][0]
        assert query_args["user_id"] == "user-123"
        assert query_args["is_active"] == True
        assert "$text" in query_args
        assert query_args["$text"]["$search"] == "office"
    
    @pytest.mark.asyncio
    async def test_increment_usage(self, mock_db):
        """Test incrementing address usage statistics"""
        service, mock_collection = mock_db
        
        # Mock successful update
        mock_collection.update_one.return_value.modified_count = 1
        
        # Test increment usage
        result = await service.increment_usage("user-123", "address-123")
        
        assert result == True
        
        # Verify update call
        mock_collection.update_one.assert_called_once()
        update_args = mock_collection.update_one.call_args[0]
        assert update_args[0]["id"] == "address-123"
        assert update_args[0]["user_id"] == "user-123"
        assert "$inc" in update_args[1]
        assert update_args[1]["$inc"]["usage_count"] == 1
        assert "$set" in update_args[1]
        assert "last_used_at" in update_args[1]["$set"]
    
    @pytest.mark.asyncio
    async def test_address_book_summary(self, mock_db):
        """Test getting address book summary"""
        service, mock_collection = mock_db
        
        # Mock addresses with different types
        mock_addresses = [
            {"address_type": "pickup", "usage_count": 5, "is_default_pickup": True},
            {"address_type": "delivery", "usage_count": 3, "is_default_delivery": True},
            {"address_type": "both", "usage_count": 10},
            {"address_type": "pickup", "usage_count": 1},
        ]
        
        mock_collection.find.return_value.to_list.return_value = mock_addresses
        
        # Test summary generation
        summary = await service.get_address_book_summary("user-123")
        
        # Verify statistics
        assert summary.total_addresses == 4
        assert summary.pickup_addresses == 3  # pickup + both
        assert summary.delivery_addresses == 2  # delivery + both
        assert summary.both_addresses == 1
        assert summary.default_pickup is not None
        assert summary.default_delivery is not None
    
    def test_to_address_dict(self, sample_saved_address):
        """Test conversion to address dictionary format"""
        from models.address_book import SavedAddressResponse
        
        address = SavedAddressResponse(**sample_saved_address)
        address_dict = address.to_address_dict()
        
        # Verify required fields are present
        required_fields = ["name", "phone", "email", "street", "city", "state", "postal_code", "country"]
        for field in required_fields:
            assert field in address_dict
        
        # Verify specific values
        assert address_dict["name"] == "John Doe"
        assert address_dict["phone"] == "+919876543210"
        assert address_dict["city"] == "Mumbai"

class TestAddressBookModels:
    """Test cases for address book models"""
    
    def test_address_type_enum(self):
        """Test AddressType enum values"""
        assert AddressType.PICKUP.value == "pickup"
        assert AddressType.DELIVERY.value == "delivery"
        assert AddressType.BOTH.value == "both"
    
    def test_address_category_enum(self):
        """Test AddressCategory enum values"""
        assert AddressCategory.HOME.value == "home"
        assert AddressCategory.OFFICE.value == "office"
        assert AddressCategory.WAREHOUSE.value == "warehouse"
        assert AddressCategory.SHOP.value == "shop"
        assert AddressCategory.OTHER.value == "other"
    
    def test_saved_address_create_defaults(self):
        """Test default values in SavedAddressCreate"""
        address = SavedAddressCreate(
            label="Test Address",
            name="Test User",
            phone="9876543210",
            email="test@example.com",
            street="Test Street 123",
            city="Mumbai",
            state="Maharashtra",
            postal_code="400001"
        )
        
        assert address.address_type == AddressType.BOTH
        assert address.category == AddressCategory.OTHER
        assert address.country == "India"
        assert address.is_default_pickup == False
        assert address.is_default_delivery == False
    
    def test_saved_address_update_optional_fields(self):
        """Test optional fields in SavedAddressUpdate"""
        update = SavedAddressUpdate(
            label="Updated Label",
            phone="8765432109"
        )
        
        assert update.label == "Updated Label"
        assert update.phone == "+918765432109"  # Should be formatted
        assert update.name is None
        assert update.email is None

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])