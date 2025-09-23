# Address Book API Documentation

The Address Book API provides comprehensive functionality for managing saved addresses for both pickup and delivery operations.

## Overview

Users can save frequently used addresses with custom labels, set default addresses, and organize addresses by categories. The system supports advanced features like search, usage tracking, and bulk operations.

## Features

- **Save Addresses**: Store pickup and delivery addresses with custom labels
- **Address Categories**: Organize addresses by type (Home, Office, Warehouse, Shop, Other)
- **Default Addresses**: Set separate default addresses for pickup and delivery
- **Usage Tracking**: Track how often addresses are used
- **Search**: Full-text search across address fields
- **Bulk Operations**: Import/export and bulk delete addresses
- **Validation**: Indian phone number and postal code validation

## API Endpoints

### Base URL
All endpoints are prefixed with `/api/address-book`

### Authentication
All endpoints require authentication via Bearer token.

---

## Address Management

### Create Address
**POST** `/addresses`

Create a new saved address.

```json
{
  "label": "Home Address",
  "address_type": "both",
  "category": "home",
  "name": "John Doe",
  "company": "Tech Corp",
  "phone": "9876543210",
  "email": "john@example.com",
  "street": "123 Tech Street, Block A",
  "city": "Mumbai",
  "state": "Maharashtra",
  "postal_code": "400001",
  "country": "India",
  "landmark": "Near Metro Station",
  "is_default_pickup": true,
  "is_default_delivery": false
}
```

**Response:**
```json
{
  "id": "address-123",
  "label": "Home Address",
  "address_type": "both",
  "category": "home",
  "name": "John Doe",
  "phone": "+919876543210",
  "email": "john@example.com",
  "street": "123 Tech Street, Block A",
  "city": "Mumbai",
  "state": "Maharashtra",
  "postal_code": "400001",
  "country": "India",
  "landmark": "Near Metro Station",
  "is_default_pickup": true,
  "is_default_delivery": false,
  "is_active": true,
  "usage_count": 0,
  "last_used_at": null,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

### Get All Addresses
**GET** `/addresses`

Get all addresses for the current user with optional filtering.

**Query Parameters:**
- `address_type`: Filter by address type (`pickup`, `delivery`, `both`)
- `category`: Filter by category (`home`, `office`, `warehouse`, `shop`, `other`)
- `is_active`: Filter by active status (default: true)
- `limit`: Number of results (max 100, default: 50)
- `offset`: Pagination offset (default: 0)

### Get Address by ID
**GET** `/addresses/{address_id}`

Get a specific address by its ID.

### Update Address
**PUT** `/addresses/{address_id}`

Update an existing address. Only provided fields will be updated.

```json
{
  "label": "Updated Home Address",
  "phone": "8765432109",
  "is_default_pickup": false
}
```

### Delete Address
**DELETE** `/addresses/{address_id}`

Soft delete an address (sets `is_active` to false).

---

## Default Addresses

### Set Default Address
**POST** `/addresses/{address_id}/set-default`

Set an address as default for pickup or delivery.

```json
{
  "address_type": "pickup"
}
```

### Get Default Addresses
**GET** `/defaults`

Get current default pickup and delivery addresses.

**Response:**
```json
{
  "pickup": {
    "id": "address-123",
    "label": "Office Address",
    // ... full address details
  },
  "delivery": {
    "id": "address-456", 
    "label": "Home Address",
    // ... full address details
  }
}
```

### Get Default Pickup Address
**GET** `/addresses/pickup/default`

Get only the default pickup address.

### Get Default Delivery Address
**GET** `/addresses/delivery/default`

Get only the default delivery address.

---

## Search and Discovery

### Search Addresses
**GET** `/addresses/search`

Search addresses using full-text search.

**Query Parameters:**
- `query`: Search term (required)
- `address_type`: Filter by address type
- `category`: Filter by category
- `limit`: Number of results (max 50, default: 20)

Example: `/addresses/search?query=office&address_type=pickup&limit=10`

### Get Recent Addresses
**GET** `/addresses/recent`

Get recently used addresses (last 30 days).

**Query Parameters:**
- `limit`: Number of results (max 20, default: 10)

### Get Frequent Addresses
**GET** `/addresses/frequent`

Get most frequently used addresses.

**Query Parameters:**
- `limit`: Number of results (max 20, default: 10)

---

## Statistics and Summary

### Get Address Book Summary
**GET** `/summary`

Get comprehensive statistics about the user's address book.

**Response:**
```json
{
  "total_addresses": 15,
  "pickup_addresses": 8,
  "delivery_addresses": 12,
  "both_addresses": 5,
  "default_pickup": {
    // default pickup address details
  },
  "default_delivery": {
    // default delivery address details
  },
  "recently_used": [
    // array of recently used addresses
  ],
  "most_used": [
    // array of most frequently used addresses
  ]
}
```

---

## Bulk Operations

### Bulk Delete Addresses
**POST** `/addresses/bulk-delete`

Delete multiple addresses at once.

```json
{
  "address_ids": ["address-123", "address-456", "address-789"]
}
```

### Import Addresses
**POST** `/import`

Import multiple addresses from a list.

```json
{
  "addresses": [
    {
      "label": "Import Address 1",
      "name": "John Doe",
      // ... other address fields
    },
    {
      "label": "Import Address 2", 
      "name": "Jane Smith",
      // ... other address fields
    }
  ],
  "skip_duplicates": true
}
```

**Response:**
```json
{
  "message": "Import completed",
  "created_count": 2,
  "skipped_count": 0,
  "errors": []
}
```

### Export Addresses
**GET** `/export`

Export all user addresses.

**Response:**
```json
{
  "addresses": [
    // array of all user addresses
  ],
  "total_count": 15,
  "export_date": "2024-01-15T10:30:00Z"
}
```

---

## Usage Tracking

### Mark Address as Used
**POST** `/addresses/{address_id}/use`

Increment usage statistics for an address. This should be called whenever an address is used in a shipment.

**Response:**
```json
{
  "message": "Usage recorded"
}
```

---

## Data Models

### Address Types
- `pickup`: Address can be used for pickup only
- `delivery`: Address can be used for delivery only  
- `both`: Address can be used for both pickup and delivery

### Address Categories
- `home`: Personal/residential address
- `office`: Business/office address
- `warehouse`: Warehouse/storage facility
- `shop`: Retail store/shop
- `other`: Other types of addresses

### Validation Rules

#### Phone Numbers
- Must be valid Indian mobile numbers
- Accepts formats: `9876543210`, `919876543210`, `+919876543210`
- Automatically formatted to `+919876543210`
- Must start with digits 6, 7, 8, or 9

#### Postal Codes
- For India: Must be exactly 6 digits
- Example: `400001`, `110001`

#### Required Fields
- `label`: User-friendly name (1-100 characters)
- `name`: Contact person name (1-100 characters)
- `phone`: Valid phone number
- `email`: Valid email address
- `street`: Street address (5-200 characters)
- `city`: City name (2-50 characters)
- `state`: State name (2-50 characters)
- `postal_code`: Valid postal code

## Error Handling

### Common Error Codes
- `400 Bad Request`: Invalid input data or validation errors
- `404 Not Found`: Address not found or doesn't belong to user
- `500 Internal Server Error`: Server-side errors

### Example Error Response
```json
{
  "detail": "Invalid Indian phone number"
}
```

## Usage Examples

### Frontend Integration

```javascript
// Create a new address
const createAddress = async (addressData) => {
  const response = await fetch('/api/address-book/addresses', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify(addressData)
  });
  return response.json();
};

// Get addresses for pickup
const getPickupAddresses = async () => {
  const response = await fetch('/api/address-book/addresses?address_type=pickup', {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  return response.json();
};

// Search addresses
const searchAddresses = async (query) => {
  const response = await fetch(`/api/address-book/addresses/search?query=${encodeURIComponent(query)}`, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  return response.json();
};
```

### Integration with Shipments

When creating a shipment, you can use saved addresses:

```javascript
// Get default addresses
const getDefaults = async () => {
  const response = await fetch('/api/address-book/defaults', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  const defaults = await response.json();
  
  if (defaults.pickup) {
    // Use default pickup address
    const pickupAddress = defaults.pickup.to_address_dict();
  }
  
  if (defaults.delivery) {
    // Use default delivery address
    const deliveryAddress = defaults.delivery.to_address_dict();
  }
};

// Mark address as used after shipment creation
const markAddressUsed = async (addressId) => {
  await fetch(`/api/address-book/addresses/${addressId}/use`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` }
  });
};
```

## Best Practices

1. **Label Addresses Clearly**: Use descriptive labels like "Home - Mumbai", "Office - Delhi"
2. **Set Defaults**: Set default pickup and delivery addresses for faster shipment creation
3. **Track Usage**: Call the usage tracking endpoint when addresses are used
4. **Validate Input**: Always validate phone numbers and postal codes on the frontend
5. **Handle Errors**: Implement proper error handling for validation failures
6. **Search Optimization**: Use the search endpoint for typeahead/autocomplete functionality
7. **Regular Cleanup**: Provide users options to delete unused addresses

## Security Notes

- All endpoints require authentication
- Users can only access their own addresses
- Soft deletion is used to maintain referential integrity
- Phone numbers are automatically formatted for consistency
- Input validation prevents malformed data