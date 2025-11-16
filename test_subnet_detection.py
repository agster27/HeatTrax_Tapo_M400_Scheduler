#!/usr/bin/env python3
"""Tests for subnet detection functions in device_discovery module."""

import unittest
from unittest.mock import patch, Mock
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from device_discovery import get_local_ip_and_subnet, is_ip_in_same_subnet


class TestSubnetDetection(unittest.TestCase):
    """Test subnet detection utility functions."""
    
    def test_is_ip_in_same_subnet_true(self):
        """Test IP is in same subnet."""
        result = is_ip_in_same_subnet(
            target_ip="192.168.1.100",
            local_ip="192.168.1.50",
            subnet_cidr="192.168.1.0/24"
        )
        self.assertTrue(result)
    
    def test_is_ip_in_same_subnet_false(self):
        """Test IP is in different subnet."""
        result = is_ip_in_same_subnet(
            target_ip="192.168.2.100",
            local_ip="192.168.1.50",
            subnet_cidr="192.168.1.0/24"
        )
        self.assertFalse(result)
    
    def test_is_ip_in_same_subnet_edge_of_range(self):
        """Test IP at edge of subnet range."""
        # First IP in range
        result = is_ip_in_same_subnet(
            target_ip="192.168.1.1",
            local_ip="192.168.1.50",
            subnet_cidr="192.168.1.0/24"
        )
        self.assertTrue(result)
        
        # Last IP in range
        result = is_ip_in_same_subnet(
            target_ip="192.168.1.254",
            local_ip="192.168.1.50",
            subnet_cidr="192.168.1.0/24"
        )
        self.assertTrue(result)
        
        # Just outside range
        result = is_ip_in_same_subnet(
            target_ip="192.168.2.1",
            local_ip="192.168.1.50",
            subnet_cidr="192.168.1.0/24"
        )
        self.assertFalse(result)
    
    def test_is_ip_in_same_subnet_different_prefix_lengths(self):
        """Test with different subnet prefix lengths."""
        # /16 subnet
        result = is_ip_in_same_subnet(
            target_ip="192.168.50.1",
            local_ip="192.168.1.50",
            subnet_cidr="192.168.0.0/16"
        )
        self.assertTrue(result)
        
        # /20 subnet
        result = is_ip_in_same_subnet(
            target_ip="10.1.5.100",
            local_ip="10.1.0.154",
            subnet_cidr="10.1.0.0/20"
        )
        self.assertTrue(result)
        
        # Outside /20 subnet
        result = is_ip_in_same_subnet(
            target_ip="10.1.20.100",
            local_ip="10.1.0.154",
            subnet_cidr="10.1.0.0/20"
        )
        self.assertFalse(result)
    
    def test_is_ip_in_same_subnet_invalid_ip(self):
        """Test with invalid IP address."""
        result = is_ip_in_same_subnet(
            target_ip="invalid.ip.address",
            local_ip="192.168.1.50",
            subnet_cidr="192.168.1.0/24"
        )
        self.assertFalse(result)
    
    def test_is_ip_in_same_subnet_invalid_subnet(self):
        """Test with invalid subnet."""
        result = is_ip_in_same_subnet(
            target_ip="192.168.1.100",
            local_ip="192.168.1.50",
            subnet_cidr="invalid/subnet"
        )
        self.assertFalse(result)
    
    @patch('device_discovery.socket.socket')
    @patch('device_discovery.subprocess.run')
    def test_get_local_ip_and_subnet_success(self, mock_run, mock_socket):
        """Test successful retrieval of local IP and subnet."""
        # Mock socket connection to determine local IP
        mock_sock = Mock()
        mock_sock.getsockname.return_value = ('192.168.1.50', 12345)
        mock_socket.return_value = mock_sock
        
        # Mock subprocess to return ip command output
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = """
1: lo: <LOOPBACK,UP,LOWER_UP>
    inet 127.0.0.1/8 scope host lo
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP>
    inet 192.168.1.50/24 brd 192.168.1.255 scope global eth0
"""
        mock_run.return_value = mock_result
        
        result = get_local_ip_and_subnet()
        
        self.assertIsNotNone(result)
        ip, subnet = result
        self.assertEqual(ip, "192.168.1.50")
        self.assertEqual(subnet, "192.168.1.0/24")
    
    @patch('device_discovery.socket.socket')
    @patch('device_discovery.subprocess.run')
    def test_get_local_ip_and_subnet_fallback_to_24(self, mock_run, mock_socket):
        """Test fallback to /24 subnet when ip command fails."""
        # Mock socket connection
        mock_sock = Mock()
        mock_sock.getsockname.return_value = ('10.1.0.154', 12345)
        mock_socket.return_value = mock_sock
        
        # Mock subprocess failure
        mock_run.side_effect = Exception("Command failed")
        
        result = get_local_ip_and_subnet()
        
        self.assertIsNotNone(result)
        ip, subnet = result
        self.assertEqual(ip, "10.1.0.154")
        self.assertEqual(subnet, "10.1.0.0/24")  # Fallback to /24
    
    @patch('device_discovery.socket.socket')
    def test_get_local_ip_and_subnet_socket_failure(self, mock_socket):
        """Test handling of socket connection failure."""
        # Mock socket to raise exception
        mock_socket.return_value.connect.side_effect = Exception("Connection failed")
        
        result = get_local_ip_and_subnet()
        
        self.assertIsNone(result)
    
    @patch('device_discovery.socket.socket')
    @patch('device_discovery.subprocess.run')
    def test_get_local_ip_and_subnet_with_different_prefixes(self, mock_run, mock_socket):
        """Test parsing different subnet prefix lengths."""
        # Mock socket connection
        mock_sock = Mock()
        mock_sock.getsockname.return_value = ('10.1.0.154', 12345)
        mock_socket.return_value = mock_sock
        
        # Mock subprocess with /20 subnet
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = """
1: lo: <LOOPBACK,UP,LOWER_UP>
    inet 127.0.0.1/8 scope host lo
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP>
    inet 10.1.0.154/20 brd 10.1.15.255 scope global eth0
"""
        mock_run.return_value = mock_result
        
        result = get_local_ip_and_subnet()
        
        self.assertIsNotNone(result)
        ip, subnet = result
        self.assertEqual(ip, "10.1.0.154")
        self.assertEqual(subnet, "10.1.0.0/20")


if __name__ == '__main__':
    unittest.main()
