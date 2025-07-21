# SPDX-FileCopyrightText: Copyright (c) 2025, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Unit tests for the redact_urls function.
"""

import os
import sys

import pytest

# Add the aira/src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from aiq_aira.utils import redact_urls


class TestRedactUrls:
    """Test cases for the redact_urls function."""

    def test_markdown_links(self):
        """Test redaction of markdown links."""
        input_text = "Check out [this link](https://example.com) for more info"
        expected = "Check out [this link](link redacted) for more info"
        assert redact_urls(input_text) == expected

    def test_markdown_links_with_complex_url(self):
        """Test redaction of markdown links with complex URLs."""
        input_text = "Here's a [reference](http://test.org/path?param=value)"
        expected = "Here's a [reference](link redacted)"
        assert redact_urls(input_text) == expected

    def test_html_links(self):
        """Test redaction of HTML anchor tags."""
        input_text = 'Visit <a href="https://example.com">our website</a> for details'
        expected = 'Visit <a href="link redacted">our website</a> for details'
        assert redact_urls(input_text) == expected

    def test_html_links_with_attributes(self):
        """Test redaction of HTML links with additional attributes."""
        input_text = 'Click <a href="http://test.org" target="_blank">here</a>'
        expected = 'Click <a href="link redacted" target="_blank">here</a>'
        assert redact_urls(input_text) == expected

    def test_html_links_with_single_quotes(self):
        """Test redaction of HTML links with single quotes."""
        input_text = "Visit <a href='https://demo.com'>demo</a>."
        result = redact_urls(input_text)
        # Accept either single or double quotes in the result
        assert "link redacted" in result
        assert "demo" in result
        assert result.startswith("Visit <a href=")
        assert result.endswith(">demo</a>.")

    def test_plain_https_urls(self):
        """Test redaction of plain HTTPS URLs."""
        input_text = "Visit https://example.com for more information"
        expected = "Visit link redacted for more information"
        assert redact_urls(input_text) == expected

    def test_plain_http_urls(self):
        """Test redaction of plain HTTP URLs."""
        input_text = "The API is at http://api.test.org/v1/endpoint"
        expected = "The API is at link redacted"
        assert redact_urls(input_text) == expected

    def test_www_urls_without_protocol(self):
        """Test redaction of www URLs without protocol."""
        input_text = "Check www.example.com for updates"
        expected = "Check link redacted for updates"
        assert redact_urls(input_text) == expected

    def test_mixed_content(self):
        """Test redaction of mixed content with multiple URL types."""
        input_text = ("Here's a [link](https://example.com) and also visit "
                      "http://test.org or www.demo.com")
        expected = ("Here's a [link](link redacted) and also visit "
                    "link redacted or link redacted")
        assert redact_urls(input_text) == expected

    def test_different_protocols(self):
        """Test redaction of URLs with different protocols."""
        input_text = "FTP: ftp://files.example.com, Mailto: mailto:user@example.com"
        expected = "FTP: link redacted, Mailto: link redacted"
        assert redact_urls(input_text) == expected

    def test_complex_markdown_with_multiple_links(self):
        """Test redaction in complex markdown with multiple link types."""
        input_text = ("# Title\n\nThis is a [link](https://example.com) and "
                      "another [one](http://test.org).\n\n"
                      "Visit <a href='https://demo.com'>demo</a>.")
        result = redact_urls(input_text)
        # Check that all URLs are redacted
        assert "[link](link redacted)" in result
        assert "[one](link redacted)" in result
        assert "link redacted" in result
        assert "demo" in result
        assert result.startswith("# Title")

    def test_no_urls(self):
        """Test text with no URLs."""
        input_text = "No URLs here"
        expected = "No URLs here"
        assert redact_urls(input_text) == expected

    def test_empty_string(self):
        """Test empty string input."""
        input_text = ""
        expected = ""
        assert redact_urls(input_text) == expected

    def test_just_text_no_links(self):
        """Test plain text with no links."""
        input_text = "Just text with no links"
        expected = "Just text with no links"
        assert redact_urls(input_text) == expected

    def test_urls_with_punctuation(self):
        """Test URLs followed by punctuation."""
        input_text = "Visit https://example.com. Then go to http://test.org!"
        result = redact_urls(input_text)
        # Check that URLs are redacted and punctuation is preserved
        assert "link redacted" in result
        assert "." in result
        assert "!" in result
        assert result.count("link redacted") == 2

    def test_urls_in_parentheses(self):
        """Test URLs within parentheses."""
        input_text = "See (https://example.com) for details"
        result = redact_urls(input_text)
        # Check that URL is redacted and parentheses are preserved
        assert "link redacted" in result
        assert "(" in result
        assert ")" in result
        assert result.count("link redacted") == 1

    def test_multiple_markdown_links_same_line(self):
        """Test multiple markdown links on the same line."""
        input_text = "[Link1](https://example1.com) and [Link2](https://example2.com)"
        expected = "[Link1](link redacted) and [Link2](link redacted)"
        assert redact_urls(input_text) == expected

    def test_html_links_with_multiple_attributes(self):
        """Test HTML links with multiple attributes."""
        input_text = '<a href="https://example.com" class="btn" id="link1">Click</a>'
        expected = '<a href="link redacted" class="btn" id="link1">Click</a>'
        assert redact_urls(input_text) == expected

    def test_urls_with_query_parameters(self):
        """Test URLs with query parameters including question marks."""
        input_text = ("Visit https://api.example.com/search?q=test&page=1 for results. "
                      "Also check http://test.org/path?param=value&other=data")
        result = redact_urls(input_text)
        # Check that URLs with query parameters are redacted
        assert "link redacted" in result
        assert result.count("link redacted") == 2
        assert "for results" in result
        assert "Also check" in result

    def test_urls_with_encoded_characters(self):
        """Test URLs with URL-encoded characters."""
        input_text = ("Check https://example.com/path%20with%20spaces and "
                      "http://test.org/file%2Fwith%2Fslashes%3Fparam%3Dvalue")
        result = redact_urls(input_text)
        # Check that URLs with encoded characters are redacted
        assert "link redacted" in result
        assert result.count("link redacted") == 2
        assert "Check" in result
        assert "and" in result

    def test_urls_with_base64_values(self):
        """Test URLs with base64 encoded values."""
        input_text = ("Download from https://files.example.com/data/YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXo= "
                      "and https://api.test.org/image/SGVsbG8gV29ybGQ=")
        result = redact_urls(input_text)
        # Check that URLs with base64 values are redacted
        assert "link redacted" in result
        assert result.count("link redacted") == 2
        assert "Download from" in result
        assert "and" in result


if __name__ == "__main__":
    # Run the tests if this file is executed directly
    pytest.main([__file__, "-v"])
